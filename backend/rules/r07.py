"""R07: URL-decoded path/query matches a web attack class from config/web_patterns.yaml."""
from ._util import finding, normalize_url

CLASS_ORDER = ["sqli", "xss", "lfi", "rfi", "cmd_injection"]
EXTRA_TECHNIQUES = {"xss": "T1059.007", "rfi": "T1105"}


def classify(text: str, cfg) -> list:
    """Attack classes whose patterns match the normalized text."""
    decoded = normalize_url(text)
    return [c for c in CLASS_ORDER
            if any(p.search(decoded) for p in cfg.classes.get(c, []))]


def evaluate(events: list, cfg) -> list:
    out = []
    for e in events:
        # blocked_request and synthetic_file_access are not request evidence for R07.
        if e["sensor_id"] != "web-decoy-01" or e["event_type"] != "http_request":
            continue
        a = e["attributes"]
        text = a.get("path", "")
        if a.get("query_redacted"):
            text += "?" + a["query_redacted"]
        classes = classify(text, cfg)
        if not classes:
            continue
        techniques = ["T1190"] + [EXTRA_TECHNIQUES[c] for c in classes if c in EXTRA_TECHNIQUES]
        out.append(finding(
            "R07", f"event={e['event_id']}",
            techniques=techniques, stage="exploit_attempt",
            label=f"Web attack attempt ({', '.join(classes)}) on {a.get('path', '')[:128]}",
            limitation="Shows an attempt only; does not show successful exploitation.",
            events=[e], web_attack_class=classes, version=2,
        ))
    return out
