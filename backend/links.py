"""Cross-decoy links. Pure functions: events in, link dicts out. Status is never set here;
only the analyst moves a link to confirmed or rejected (db.decide_link)."""
import hashlib

from .rules._util import in_order, ts

SENSOR_PAIR = ("ssh-decoy-01", "web-decoy-01")


def link_id(key: str) -> str:
    return "lnk_" + hashlib.sha256(key.encode()).hexdigest()[:10]


def _link(key, frm, to, kind, basis):
    return {
        "link_id": link_id(key), "from_event_id": frm["event_id"], "to_event_id": to["event_id"],
        "from_sensor": frm["sensor_id"], "to_sensor": to["sensor_id"], "kind": kind, "basis": basis,
        "from_incident_id": frm["incident_id"], "to_incident_id": to["incident_id"],
    }


def candidate_links(incident_id: str, events: list, cfg) -> list:
    """Same src_ip (= same incident) seen on both sensors within the window: one candidate,
    from the earliest qualifying pair."""
    secs = cfg.windows["link_candidate_seconds"]
    last: dict = {}
    for e in in_order([e for e in events if e["event_type"] != "blocked_request"]):
        other = SENSOR_PAIR[1] if e["sensor_id"] == SENSOR_PAIR[0] else SENSOR_PAIR[0]
        prev = last.get(other)
        if prev and (ts(e) - ts(prev)).total_seconds() <= secs:
            return [_link(f"candidate|{incident_id}", prev, e, "candidate",
                          f"same src_ip within {secs // 60} min")]
        last[e["sensor_id"]] = e
    return []


def strong_links(uses: list, planted_lookup, cfg) -> list:
    """`uses`: events presenting a honeytoken on a sensor other than where it was planted.
    `planted_lookup(token, use_event)` returns the planted-sensor event to link from, or None."""
    out, seen = [], set()
    for e in in_order(uses):
        tok_id = e["attributes"]["honeytoken_id"]
        key = f"strong|{tok_id}|{e['incident_id']}"
        if key in seen:
            continue
        frm = planted_lookup(cfg.honeytokens[tok_id], e)
        if frm:
            seen.add(key)
            out.append(_link(key, frm, e, "strong_candidate", f"honeytoken {tok_id}"))
    return out


def token_uses(events: list, cfg) -> list:
    out = []
    for e in events:
        tok = cfg.honeytokens.get(e["attributes"].get("honeytoken_id", ""))
        if tok and e["event_type"] != "blocked_request" and e["sensor_id"] != tok["planted_on"]:
            out.append(e)
    return out
