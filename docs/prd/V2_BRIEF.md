# DeceptionGraph v2: project brief (defensive security tooling)

Status: draft, 31 Oct 2026. Starting point: the v1 hackathon code in
`rohanol/decoy-hackathon-demo` (commit `fb227bb`, folder `dg-soc/`), copied into this repo.

## Scope and intent

An authorized defensive security project: a deception sensor kit ("honeypot" kit) that an
organization installs inside its OWN network to detect intruders early. Same category as
Thinkst Canary and MITRE Engage. It only observes, classifies and alerts on activity against
decoy systems the organization deploys on its own infrastructure. No offensive, exploitation
or retaliatory capability: it never attacks, never "hacks back", never damages any device,
and never executes anything an intruder submits.

## Why it works

The decoys have no legitimate users, so any interaction with a decoy is suspicious by
definition. False positives are close to zero, and the security team watches a small number
of high-confidence signals instead of millions of real events.

## What we ship (one `docker compose up`)

1. Two decoys (containers):
   - SSH decoy (Cowrie, emulated shell): login attempts, brute force, commands typed into a
     fake shell. Nothing runs on a real host.
   - Fake internal web portal: believable but fake pages; records web attack attempts (SQL
     injection, XSS, file inclusion, hidden-path probing, fake API/IDOR endpoints such as
     `/api/orders/{id}`, downloads of decoy files).
2. Log adapter: reads each decoy's logs, classifies the activity (event type and, for web,
   the attack class), normalizes it to the shared event schema, redacts captured passwords,
   sends it to the backend.
3. Backend (FastAPI + SQLite): ingests, deduplicates, groups into one incident per source IP
   per deployment, runs deterministic rules, scores from versioned config, links activity
   across both decoys when a planted honeytoken is reused, serves a read API and a live stream.
4. SOC dashboard: a detailed per-incident view and a simplified at-a-glance view.

## Honeytoken bait (non-destructive signal)

The web decoy serves small, realistic decoy files (for example a fake `customer_export.csv`
or a config with planted credentials), each carrying a honeytoken. Downloading a bait file,
or reusing a planted credential on the SSH decoy, raises a high-confidence finding and draws a
cross-decoy link tying both sightings to one source. The bait is a tracker, not a payload.
Explicitly excluded: any file meant to exhaust disk or memory or crash a visitor's machine.

## Backend (M3): what to build

Stack: FastAPI + Pydantic + SQLite (WAL, single writer). Small, offline, one container.

Key change from v1: remove lab assumptions. v1 assumed one fixed attacker IP and one lab run.
In a real deployment every source IP that touches a decoy opens or extends an incident.
Replace the lab-run identifier with a per-install `deployment_id` (+ optional `site` label);
bump the event schema to `"2.0"`.

Pipeline:

```
ingest (validate, dedup by source_record_id, redact secrets, assign id + sequence)
  -> group into incident by (deployment_id, src_ip)
  -> deterministic rules -> findings
  -> score from versioned config (capped)
  -> cross-decoy links via honeytoken reuse
  -> persist + push over /ws/events to the dashboard
```

- Reuse from v1: routes, DB schema, models, scoring, links, rules R01-R09, the live stream.
- Change: drop the attacker-IP gate; group per deployment; cap the stored size of
  attacker-controlled strings (commands, paths, queries).
- Add: `deployments` table; a rule for hits on planted/IDOR/hidden endpoints (path pattern
  match only); generalized honeytoken tracking; `/api/summary` for the simple view;
  `/api/deployments` for decoy health.

AI enrichment: the deterministic classifier stays the source of truth because scores and
labels cite it. AI may be added later as optional plain-English enrichment, marked as
model-generated, never feeding the score. Not needed for the first working version.

## Safety and honesty rules

- Decoys stay emulated and isolated; the backend and dashboard are never reachable from the
  decoy network.
- Passwords and tokens are redacted before storage; attacker input is never executed and
  attacker-referenced URLs are never fetched.
- Labels match evidence: "command submitted to an emulated shell", "synthetic file served",
  "web attack attempt", "honeytoken reuse". Never "compromised" or "attacker isolated".
- No destructive or retaliatory behavior of any kind.

## Build order

1. Contract PR: event schema v2 (`deployment_id`/`site`, `schema_version` `"2.0"`, new rule
   ids, new endpoints). Merge first so the team rebases on it.
2. Ingest + per-deployment grouping, size cap, deployments table. Runs on fixtures.
3. Rules: port R01-R09, add the IDOR/hidden-endpoint rule, generalize honeytoken linking.
4. `/api/summary` and `/api/deployments` for the simple dashboard view.
5. Backend in the one-command Compose stack with a persistent volume + retention.
6. A test per rule/endpoint including a negative case, then an end-to-end replay. Always run
   the app and tests and report the real output.
