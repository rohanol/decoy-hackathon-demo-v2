"""Incident score from config/scoring.yaml. Pure: findings + links in, score out.

- each rule counts once per incident, at its configured weight
- R05/R09 (needs_confirmation) count only after the analyst confirms the link
- total capped at cfg.cap; every finding gets a breakdown row saying why
"""
def severity_for(score: int, cfg) -> str:
    best = "low"
    for name, lower in sorted(cfg.severity.items(), key=lambda kv: kv[1]):
        if score >= lower:
            best = name
    return best


def _confirmed(f: dict, links: list) -> bool:
    if f["rule_id"] == "R05":
        return True  # R05 only exists for a confirmed link
    if f["rule_id"] == "R09":
        cited = set(f["evidence_event_ids"])
        return any(l["status"] == "confirmed" and l["kind"] == "strong_candidate"
                   and l["to_event_id"] in cited for l in links)
    return False


def score_incident(findings: list, links: list, cfg) -> dict:
    """`findings` must be in the order they were first recorded, so the finding that arrives
    last is the one the cap trims. Returns {"score", "severity", "breakdown",
    "points": {finding_id: (points, pending)}}."""
    total, counted_rules, rows, points = 0, set(), [], {}
    for f in findings:
        rule, weight = f["rule_id"], cfg.weights.get(f["rule_id"], 0)
        pending = rule in cfg.needs_confirmation and not _confirmed(f, links)
        counted = False
        if pending:
            give, reason = 0, f"{rule} waits for the analyst to confirm the link"
        elif rule in counted_rules:
            give, reason = 0, f"{rule} already counted for this incident"
        else:
            counted = True
            counted_rules.add(rule)
            give = min(weight, cfg.cap - total)
            reason = f"first {rule}"
            if give < weight:
                reason += f" (weight {weight}, capped at {cfg.cap})"
        total += give
        rows.append({"rule_id": rule, "points": give, "counted": counted, "reason": reason,
                     "finding_id": f["finding_id"]})
        points[f["finding_id"]] = (give, pending)
    return {"score": total, "severity": severity_for(total, cfg), "breakdown": rows, "points": points}
