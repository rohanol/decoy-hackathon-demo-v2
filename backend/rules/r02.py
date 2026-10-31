"""R02: command_input in an SSH session that had auth_success."""
from ._util import finding, in_order, ts


def evaluate(events: list, cfg) -> list:
    ssh = in_order([e for e in events if e["sensor_id"] == "ssh-decoy-01" and e["session_id"]])
    out = []
    for sid in sorted({e["session_id"] for e in ssh}):
        sess = [e for e in ssh if e["session_id"] == sid]
        logins = [e for e in sess if e["event_type"] == "auth_success"]
        if not logins:
            continue
        cmds = [e for e in sess if e["event_type"] == "command_input" and ts(e) >= ts(logins[0])]
        if cmds:
            out.append(finding(
                "R02", f"session={sid}",
                techniques=["T1059.004"], stage="post_access",
                label=f"Command submitted to an emulated shell after login ({len(cmds)} command(s))",
                limitation="The shell is emulated; this does not show real command execution.",
                events=[logins[0]] + cmds,
            ))
    return out
