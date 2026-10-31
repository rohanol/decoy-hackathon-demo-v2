"""R01: 5+ SSH auth failures, same src_ip + username, within 60 s (inclusive).

If the decoy then accepts a login for that same username within another 60 s, the label
says so and that login is cited as evidence (the guessing-then-success pattern behind
rules such as Elastic's "Potential Successful SSH Brute Force"). Points do not change.
"""
from ._util import MAX_EVIDENCE, finding, first_window, in_order, ts


def _accepted_after(events: list, user: str, window: list, secs: int):
    last = ts(window[-1])
    for e in in_order(events):
        if (e["sensor_id"] == "ssh-decoy-01" and e["event_type"] == "auth_success"
                and e["attributes"].get("username", "") == user
                and 0 <= (ts(e) - last).total_seconds() <= secs):
            return e
    return None


def evaluate(events: list, cfg) -> list:
    n = cfg.windows["r01_threshold"]
    secs = cfg.windows["r01_seconds"]
    by_user: dict = {}
    for e in events:
        if e["sensor_id"] == "ssh-decoy-01" and e["event_type"] == "auth_failure":
            by_user.setdefault(e["attributes"].get("username", ""), []).append(e)
    out = []
    for user, fails in sorted(by_user.items()):
        window = first_window(fails, n, secs)
        if not window:
            continue
        label = f"Repeated SSH password guessing ({len(window)} failures in {secs} s) for user '{user[:64]}'"
        evidence = window
        accepted = _accepted_after(events, user, window, secs)
        if accepted:
            gap = int((ts(accepted) - ts(window[-1])).total_seconds())
            label += f"; the decoy accepted a login for this user {gap} s later"
            evidence = window[:MAX_EVIDENCE - 1] + [accepted]  # keep the login inside the cap
        out.append(finding(
            "R01", f"user={user}",
            techniques=["T1110.001"], stage="credential_attack",
            label=label,
            limitation="Does not show that the account was compromised.",
            events=evidence, version=2,
        ))
    return out
