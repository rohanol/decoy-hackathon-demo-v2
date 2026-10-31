"""SQLite (WAL) storage. One writer behind a lock; one read connection per thread."""
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import links as linking
from .config import Config, load_config
from .models import IngestEvent, to_rfc3339
from .rules import evaluate_incident
from .scoring import score_incident

DEFAULT_DB = Path(__file__).parent / "data" / "dg.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    src_ip      TEXT NOT NULL,
    lab_run_id  TEXT NOT NULL,
    score       INTEGER NOT NULL DEFAULT 0,
    severity    TEXT NOT NULL DEFAULT 'low',
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (src_ip, lab_run_id)
);
CREATE TABLE IF NOT EXISTS events (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id         TEXT NOT NULL UNIQUE,
    sensor_id        TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    occurred_at      TEXT NOT NULL,
    ingested_at      TEXT NOT NULL,
    src_ip           TEXT NOT NULL,
    src_port         INTEGER,
    session_id       TEXT,
    lab_run_id       TEXT NOT NULL,
    capture_mode     TEXT NOT NULL,
    attributes       TEXT NOT NULL,
    incident_id      TEXT NOT NULL REFERENCES incidents(incident_id),
    UNIQUE (sensor_id, source_record_id)
);
CREATE INDEX IF NOT EXISTS idx_events_incident ON events(incident_id, seq);
CREATE TABLE IF NOT EXISTS findings (
    finding_id  TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
    rule_id     TEXT NOT NULL,
    data        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_incident ON findings(incident_id);
CREATE TABLE IF NOT EXISTS links (
    link_id          TEXT PRIMARY KEY,
    from_event_id    TEXT NOT NULL,
    to_event_id      TEXT NOT NULL,
    from_sensor      TEXT NOT NULL,
    to_sensor        TEXT NOT NULL,
    kind             TEXT NOT NULL,
    basis            TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'open',
    decided_at       TEXT,
    rationale        TEXT,
    from_incident_id TEXT NOT NULL,
    to_incident_id   TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
"""

SENSORS = ("ssh-decoy-01", "web-decoy-01")
STAGE_ORDER = ["recon", "credential_attack", "exploit_attempt", "post_access", "data_access"]
LINK_FIELDS = ["link_id", "from_event_id", "to_event_id", "from_sensor", "to_sensor",
               "kind", "basis", "status", "decided_at", "rationale"]
TRANSCRIPT_KINDS = {"auth_failure": "login_failed", "auth_success": "login_ok",
                    "command_input": "command", "connection_close": "close"}


def _now() -> str:
    """Backend-issued timestamps (ingested_at, created_at, decided_at): UTC, milliseconds."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class Database:
    """One writer connection (behind a lock) plus one read connection per thread.

    WAL lets readers run while a write is in progress, and a reader only ever sees
    committed data, so a GET can never return a half-written ingest."""

    def __init__(self, path: Optional[str] = None, cfg: Optional[Config] = None):
        self.cfg = cfg or load_config()
        self.path = path or os.environ.get("DG_DB_PATH") or str(DEFAULT_DB)
        if self.path == ":memory:":
            raise ValueError("use a file path: readers and the writer need to share one database")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._writer = self._connect()
        self._writer.execute("PRAGMA journal_mode=WAL")
        self._writer.executescript(SCHEMA)
        self._write_lock = threading.Lock()
        self._local = threading.local()
        self._readers: list[sqlite3.Connection] = []
        self._readers_lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        # isolation_level=None: autocommit for reads; the writer issues BEGIN/COMMIT itself.
        conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        """Read connection for the calling thread."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
            with self._readers_lock:
                self._readers.append(conn)
        return conn

    def close(self) -> None:
        with self._readers_lock:
            for conn in self._readers:
                conn.close()
            self._readers.clear()
        self._writer.close()

    def _write(self, fn):
        """Run fn(conn) in one IMMEDIATE transaction under the single-writer lock."""
        with self._write_lock:
            c = self._writer
            c.execute("BEGIN IMMEDIATE")
            try:
                result = fn(c)
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return result

    # ---- writes ----
    def ingest(self, events: list[IngestEvent]) -> dict:
        """Insert events, then links, rules and scores, all in ONE transaction.
        Returns {"stored": [event dict or None for a duplicate], "links": [new links],
        "findings": [new or changed findings], "incidents": [touched incident ids]}.
        The caller broadcasts afterwards."""
        def work(c):
            touched: set[str] = set()
            stored = [self._insert_one(c, ev, touched) for ev in events]
            # Load each touched incident's events once; links and rules both use them.
            loaded = {inc: self._incident_events(c, inc) for inc in sorted(touched)}
            new_links = self._refresh_links(c, loaded)
            affected = set(touched)
            for l in new_links:
                affected.update((l["from_incident_id"], l["to_incident_id"]))
            changed = [f for inc in sorted(affected) for f in self._sync_incident(c, inc, loaded.get(inc))]
            return {"stored": stored, "links": new_links, "findings": changed,
                    "incidents": sorted(affected) if any(stored) or new_links else []}
        return self._write(work)

    def decide_link(self, link_id: str, decision: str, rationale: str) -> Optional[dict]:
        """Analyst decision. Re-runs rules and scores for both linked incidents."""
        def work(c):
            row = c.execute("SELECT * FROM links WHERE link_id=?", (link_id,)).fetchone()
            if not row:
                return None
            status = "confirmed" if decision == "confirm" else "rejected"
            c.execute("UPDATE links SET status=?, decided_at=?, rationale=? WHERE link_id=?",
                      (status, _now(), rationale, link_id))
            affected = sorted({row["from_incident_id"], row["to_incident_id"]})
            changed = [f for inc in affected for f in self._sync_incident(c, inc)]
            link = dict(c.execute("SELECT * FROM links WHERE link_id=?", (link_id,)).fetchone())
            return {"link": link, "findings": changed, "incidents": affected}
        return self._write(work)

    def _insert_one(self, c: sqlite3.Connection, ev: IngestEvent, touched: set[str]) -> Optional[dict]:
        dup = c.execute(
            "SELECT 1 FROM events WHERE sensor_id=? AND source_record_id=?",
            (ev.sensor_id, ev.source_record_id),
        ).fetchone()
        if dup:
            return None
        occurred = to_rfc3339(ev.occurred_at)
        row = c.execute(
            "SELECT incident_id FROM incidents WHERE src_ip=? AND lab_run_id=?",
            (ev.src_ip, ev.lab_run_id),
        ).fetchone()
        if row:
            incident_id = row["incident_id"]
            c.execute(
                "UPDATE incidents SET event_count=event_count+1, "
                "first_seen=MIN(first_seen, ?), last_seen=MAX(last_seen, ?) WHERE incident_id=?",
                (occurred, occurred, incident_id),
            )
        else:
            cur = c.execute(
                "INSERT INTO incidents (incident_id, src_ip, lab_run_id, first_seen, last_seen, event_count) "
                "VALUES ('pending', ?, ?, ?, ?, 1)",
                (ev.src_ip, ev.lab_run_id, occurred, occurred),
            )
            incident_id = f"inc_{cur.lastrowid:02d}"
            c.execute("UPDATE incidents SET incident_id=? WHERE rowid=?", (incident_id, cur.lastrowid))
        touched.add(incident_id)
        event_id = "evt_" + uuid.uuid4().hex[:12]
        attrs = ev.attributes.model_dump(exclude_none=True)
        cur = c.execute(
            "INSERT INTO events (event_id, sensor_id, source_record_id, event_type, occurred_at, ingested_at, "
            "src_ip, src_port, session_id, lab_run_id, capture_mode, attributes, incident_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event_id, ev.sensor_id, ev.source_record_id, ev.event_type, occurred, _now(),
             ev.src_ip, ev.src_port, ev.session_id, ev.lab_run_id, ev.capture_mode,
             json.dumps(attrs), incident_id),
        )
        return self._event_dict(c.execute("SELECT * FROM events WHERE seq=?", (cur.lastrowid,)).fetchone())

    def _incident_events(self, c, incident_id: str) -> list[dict]:
        return [self._event_dict(r) for r in
                c.execute("SELECT * FROM events WHERE incident_id=? ORDER BY seq", (incident_id,))]

    def _refresh_links(self, c, loaded: dict) -> list[dict]:
        """`loaded`: incident_id -> its events, for the incidents this ingest touched."""
        def planted_lookup(tok: dict, use: dict) -> Optional[dict]:
            # Prefer the same src_ip, then a shell command (e.g. reading the bait file), then latest.
            r = c.execute(
                "SELECT * FROM events WHERE sensor_id=? AND lab_run_id=? AND occurred_at<=? "
                "AND event_type != 'blocked_request' "
                "ORDER BY (src_ip=?) DESC, (event_type='command_input') DESC, occurred_at DESC, seq DESC LIMIT 1",
                (tok["planted_on"], use["lab_run_id"], use["occurred_at"], use["src_ip"]),
            ).fetchone()
            return self._event_dict(r) if r else None

        new = []
        for inc, events in loaded.items():
            found = linking.candidate_links(inc, events, self.cfg)
            found += linking.strong_links(linking.token_uses(events, self.cfg), planted_lookup, self.cfg)
            for l in found:
                cur = c.execute(
                    "INSERT OR IGNORE INTO links (link_id, from_event_id, to_event_id, from_sensor, to_sensor, "
                    "kind, basis, from_incident_id, to_incident_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (l["link_id"], l["from_event_id"], l["to_event_id"], l["from_sensor"], l["to_sensor"],
                     l["kind"], l["basis"], l["from_incident_id"], l["to_incident_id"], _now()),
                )
                if cur.rowcount:
                    new.append(dict(c.execute("SELECT * FROM links WHERE link_id=?", (l["link_id"],)).fetchone()))
        return new

    def _links_for(self, c, incident_id: str) -> list[dict]:
        return [dict(r) for r in c.execute(
            "SELECT * FROM links WHERE from_incident_id=? OR to_incident_id=? ORDER BY created_at, link_id",
            (incident_id, incident_id))]

    def _sync_incident(self, c, incident_id: str, events: Optional[list] = None) -> list[dict]:
        """Re-run rules and scoring for one incident; store and return what changed."""
        inc = c.execute("SELECT incident_id, src_ip FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        links = self._links_for(c, incident_id)
        if events is None:
            events = self._incident_events(c, incident_id)
        fresh = evaluate_incident(dict(inc), events, self.cfg, links)
        # rowid = order first recorded; scoring walks findings in that order (new ones last).
        existing = {r["finding_id"]: json.loads(r["data"]) for r in c.execute(
            "SELECT finding_id, data FROM findings WHERE incident_id=? ORDER BY rowid", (incident_id,))}
        rank = {fid: i for i, fid in enumerate(existing)}
        fresh.sort(key=lambda f: rank.get(f["finding_id"], len(rank)))  # stable: new ones keep rule order
        for f in fresh:
            f["created_at"] = existing[f["finding_id"]]["created_at"] if f["finding_id"] in existing else _now()
        scored = score_incident(fresh, links, self.cfg)
        changed = []
        for f in fresh:
            f["points"], f["pending_confirmation"] = scored["points"][f["finding_id"]]
            if existing.get(f["finding_id"]) == f:
                continue
            c.execute(
                "INSERT INTO findings (finding_id, incident_id, rule_id, data, created_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(finding_id) DO UPDATE SET data=excluded.data",
                (f["finding_id"], incident_id, f["rule_id"], json.dumps(f), f["created_at"]),
            )
            changed.append(f)
        stale = set(existing) - {f["finding_id"] for f in fresh}  # e.g. R05 after a link is rejected
        for fid in stale:
            c.execute("DELETE FROM findings WHERE finding_id=?", (fid,))
        c.execute("UPDATE incidents SET score=?, severity=? WHERE incident_id=?",
                  (scored["score"], scored["severity"], incident_id))
        return changed

    # ---- reads ----
    @staticmethod
    def _event_dict(r: sqlite3.Row) -> dict:
        return {
            "schema_version": "1.0",
            "event_id": r["event_id"],
            "seq": r["seq"],
            "ingested_at": r["ingested_at"],
            "incident_id": r["incident_id"],
            "source_record_id": r["source_record_id"],
            "sensor_id": r["sensor_id"],
            "event_type": r["event_type"],
            "occurred_at": r["occurred_at"],
            "src_ip": r["src_ip"],
            "src_port": r["src_port"],
            "session_id": r["session_id"],
            "lab_run_id": r["lab_run_id"],
            "capture_mode": r["capture_mode"],
            "attributes": json.loads(r["attributes"]),
        }

    @staticmethod
    def public_link(link: dict) -> dict:
        return {k: link[k] for k in LINK_FIELDS}

    def list_events(self, incident_id=None, sensor_id=None, since_seq=0, limit=200) -> dict:
        sql, args = "SELECT * FROM events WHERE seq > ?", [since_seq]
        if incident_id:
            sql += " AND incident_id=?"
            args.append(incident_id)
        if sensor_id:
            sql += " AND sensor_id=?"
            args.append(sensor_id)
        sql += " ORDER BY seq ASC LIMIT ?"
        args.append(limit)
        items = [self._event_dict(r) for r in self.conn.execute(sql, args)]
        return {"items": items, "next_seq": items[-1]["seq"] if items else since_seq}

    def max_seq(self) -> int:
        return self.conn.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0]

    def incident_exists(self, incident_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM incidents WHERE incident_id=?", (incident_id,)).fetchone() is not None

    def incident_summary(self, incident_id: str) -> dict:
        r = self.conn.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        return {
            "incident_id": r["incident_id"], "src_ip": r["src_ip"], "lab_run_id": r["lab_run_id"],
            "score": r["score"], "severity": r["severity"],
            "stages_observed": self._stages(incident_id),
            "first_seen": r["first_seen"], "last_seen": r["last_seen"], "event_count": r["event_count"],
        }

    @contextmanager
    def snapshot(self):
        """Several reads that must agree with each other see one committed state."""
        c = self.conn
        if c.in_transaction:
            yield
            return
        c.execute("BEGIN")
        try:
            yield
        finally:
            c.execute("COMMIT")

    def list_incidents(self) -> list[dict]:
        with self.snapshot():
            ids = [r[0] for r in self.conn.execute(
                "SELECT incident_id FROM incidents ORDER BY last_seen DESC, rowid DESC")]
            return [self.incident_summary(i) for i in ids]

    def list_findings(self, incident_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT data FROM findings WHERE incident_id=? ORDER BY rowid", (incident_id,))
        return [json.loads(r["data"]) for r in rows]

    def list_links(self, incident_id: Optional[str] = None) -> list[dict]:
        if incident_id:
            rows = self._links_for(self.conn, incident_id)
        else:
            rows = [dict(r) for r in self.conn.execute("SELECT * FROM links ORDER BY created_at, link_id")]
        return [self.public_link(r) for r in rows]

    def _stages(self, incident_id: str) -> list[str]:
        seen = {f["stage"] for f in self.list_findings(incident_id)}
        return [s for s in STAGE_ORDER if s in seen]

    def sessions(self, incident_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT session_id, sensor_id, MIN(occurred_at) AS started_at, "
            "SUM(event_type='command_input') AS commands FROM events "
            "WHERE incident_id=? AND session_id IS NOT NULL GROUP BY sensor_id, session_id "
            "ORDER BY started_at, session_id", (incident_id,))
        return [dict(r) for r in rows]

    def incident_detail(self, incident_id: str) -> dict:
        """Incident minus `summary` and `active_block`, which main.py adds."""
        with self.snapshot():
            findings = self.list_findings(incident_id)
            links = self._links_for(self.conn, incident_id)
            out = self.incident_summary(incident_id)
            out.update({
                "findings": findings,
                "score_breakdown": score_incident(findings, links, self.cfg)["breakdown"],
                "links": [self.public_link(l) for l in links],
                "sessions": self.sessions(incident_id),
            })
            return out

    def transcript(self, incident_id: str, session_id: Optional[str]) -> Optional[dict]:
        if not session_id:
            # Default: the first session that logged in, else the first session at all.
            r = self.conn.execute(
                "SELECT session_id FROM events WHERE incident_id=? AND sensor_id='ssh-decoy-01' "
                "AND session_id IS NOT NULL ORDER BY (event_type='auth_success') DESC, occurred_at, seq LIMIT 1",
                (incident_id,)).fetchone()
            if not r:
                return {"session_id": None, "lines": []}
            session_id = r["session_id"]
        rows = self.conn.execute(
            "SELECT * FROM events WHERE incident_id=? AND sensor_id='ssh-decoy-01' AND session_id=? "
            "ORDER BY occurred_at, seq", (incident_id, session_id)).fetchall()
        if not rows:
            return None
        lines = []
        for r in rows:
            kind = TRANSCRIPT_KINDS.get(r["event_type"])
            if not kind:
                continue
            a = json.loads(r["attributes"])
            user = a.get("username", "")
            text = {
                "login_failed": f"login failed for user '{user}'",
                "login_ok": f"login accepted for user '{user}'",
                "command": a.get("command", ""),
                "close": "session closed",
            }[kind]
            lines.append({"event_id": r["event_id"], "occurred_at": r["occurred_at"], "kind": kind, "text": text})
        return {"session_id": session_id, "lines": lines}

    def stats(self) -> dict:
        c = self.conn
        with self.snapshot():
            by_rule = {r["rule_id"]: r["n"] for r in
                       c.execute("SELECT rule_id, COUNT(*) AS n FROM findings GROUP BY rule_id ORDER BY rule_id")}
            first = c.execute("SELECT incident_id, created_at FROM findings ORDER BY created_at LIMIT 1").fetchone()
            first_alert = None
            if first:
                # From the backend receiving that incident's first event to its first finding.
                start = c.execute("SELECT MIN(ingested_at) FROM events WHERE incident_id=?",
                                  (first["incident_id"],)).fetchone()[0]
                first_alert = round(max(0.0, (_ts(first["created_at"]) - _ts(start)).total_seconds()), 3)
            return {
                "raw_events": c.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                "incidents": c.execute("SELECT COUNT(*) FROM incidents").fetchone()[0],
                "low_priority_incidents": c.execute("SELECT COUNT(*) FROM incidents WHERE score < ?",
                                                    (self.cfg.low_priority_below,)).fetchone()[0],
                "findings_by_rule": by_rule,
                "first_alert_seconds": first_alert,
            }

    def export_events(self, incident_id: str) -> list[dict]:
        """Incident events for export with password hashes removed."""
        out = []
        for e in self.list_events(incident_id=incident_id, limit=1_000_000)["items"]:
            e["attributes"] = {k: v for k, v in e["attributes"].items() if k != "password_sha256"}
            out.append(e)
        return out

    def sensor_last_seen(self) -> dict:
        out = {s: None for s in SENSORS}
        for r in self.conn.execute("SELECT sensor_id, MAX(occurred_at) AS t FROM events GROUP BY sensor_id"):
            out[r["sensor_id"]] = r["t"]
        return out
