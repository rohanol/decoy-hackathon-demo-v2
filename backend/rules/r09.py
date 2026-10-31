"""R09: a honeytoken planted on one sensor is presented on the other sensor.

Counts for score only after the analyst confirms the strong_candidate link (scoring.py).
"""
from ._util import finding, in_order


def evaluate(events: list, cfg) -> list:
    uses: dict = {}
    for e in in_order(events):
        tok_id = e["attributes"].get("honeytoken_id")
        tok = cfg.honeytokens.get(tok_id) if tok_id else None
        if tok and e["event_type"] != "blocked_request" and e["sensor_id"] != tok["planted_on"]:
            uses.setdefault(tok_id, []).append(e)
    out = []
    for tok_id, evs in sorted(uses.items()):
        tok = cfg.honeytokens[tok_id]
        out.append(finding(
            "R09", f"token={tok_id}",
            techniques=[], stage="none",
            label=f"Honeytoken {tok_id} presented on {evs[0]['sensor_id']} (planted on {tok['planted_on']})",
            limitation="Token reuse does not show that it is the same person.",
            events=evs,
        ))
    return out
