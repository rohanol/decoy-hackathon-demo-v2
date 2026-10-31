"""R03: a submitted command starts with `ls` or `find`.

Each part of a chained line counts on its own (`cd /tmp; ls -la`, `id && find / -name x`),
and so do full paths and sudo (`/bin/ls`, `sudo find`), which is how shell-command
detections such as Sigma's Linux discovery rules read a command line.
"""
import re

from ._util import finding, in_order

SEGMENTS = re.compile(r"\s*(?:;|&&|\|\||\||&|\n)\s*")
# sudo flags may take a value (`sudo -u root find`); the regex backtracks if that "value" is the command.
DISCOVERY = re.compile(r"^(?:sudo(?:\s+-\S+(?:\s+[^-\s]\S*)?)*\s+)?(?:\S*/)?(ls|find)(\s|$)")


def is_discovery(command: str) -> bool:
    return any(DISCOVERY.match(part) for part in SEGMENTS.split(command.strip()))


def evaluate(events: list, cfg) -> list:
    ssh = in_order([e for e in events if e["sensor_id"] == "ssh-decoy-01"
                    and e["event_type"] == "command_input"])
    out = []
    for sid in sorted({e["session_id"] or "" for e in ssh}):
        hits = [e for e in ssh if (e["session_id"] or "") == sid
                and is_discovery(e["attributes"].get("command", ""))]
        if hits:
            out.append(finding(
                "R03", f"session={sid}",
                techniques=["T1083"], stage="post_access",
                label=f"Discovery command (ls/find) submitted to an emulated shell ({len(hits)} command(s))",
                limitation="Shows a discovery attempt only.",
                events=hits, version=2,
            ))
    return out
