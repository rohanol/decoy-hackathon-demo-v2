"""Rule engine. Event rules expose evaluate(events, cfg) -> list of finding dicts;
R05 reads the incident's links instead (evaluate(incident_id, links))."""
import hashlib

from . import r01, r02, r03, r04, r05, r07, r08, r09

RULES = [r01, r02, r03, r04, r07, r08, r09]


def finding_id(incident_id: str, rule_id: str, key: str) -> str:
    digest = hashlib.sha256(f"{incident_id}|{rule_id}|{key}".encode()).hexdigest()
    return "fnd_" + digest[:12]


def evaluate_incident(incident: dict, events: list, cfg, links: list = ()) -> list:
    """All findings for one incident, with stable ids. `incident` needs incident_id, src_ip."""
    raw = [f for rule in RULES for f in rule.evaluate(events, cfg)]
    raw += r05.evaluate(incident["incident_id"], list(links))
    out = []
    for f in raw:
        f = dict(f)
        key = f.pop("key")
        f["finding_id"] = finding_id(incident["incident_id"], f["rule_id"], key)
        f["incident_id"] = incident["incident_id"]
        f["src_ip"] = incident["src_ip"]
        out.append(f)
    return out
