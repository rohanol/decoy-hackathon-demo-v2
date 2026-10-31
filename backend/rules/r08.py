"""R08: 5+ hidden-path requests in 60 s, or 10+ HTTP 404s in 60 s, from one src_ip.

A request counts as hidden-path when its normalized path is a listed path or sits under
one (`/admin/login.php` is under `/admin`), the way scanners such as dirb and gobuster probe.
"""
from ._util import finding, first_window, normalize_path


def is_hidden(path: str, hidden_paths) -> bool:
    p = normalize_path(path)
    return any(p == h or p.startswith(h + "/") for h in hidden_paths)


def evaluate(events: list, cfg) -> list:
    web = [e for e in events if e["sensor_id"] == "web-decoy-01" and e["event_type"] == "http_request"]
    secs = cfg.windows["r08_seconds"]
    hidden = [e for e in web if is_hidden(e["attributes"].get("path", ""), cfg.hidden_paths)]
    not_found = [e for e in web if e["attributes"].get("status_code") == 404]
    out = []
    window = first_window(hidden, cfg.windows["r08_hidden_threshold"], secs)
    kind = "hidden-path requests"
    if not window:
        window = first_window(not_found, cfg.windows["r08_404_threshold"], secs)
        kind = "404 responses"
    if window:
        out.append(finding(
            "R08", "probing",
            techniques=["T1595.003"], stage="recon",
            label=f"Web path probing ({len(window)} {kind} in {secs} s)",
            limitation="A request pattern only; does not show a network scan.",
            events=window, version=2,
        ))
    return out
