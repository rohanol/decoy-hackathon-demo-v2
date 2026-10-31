"""R04: synthetic_file_access with outcome == served."""
from ._util import finding


def evaluate(events: list, cfg) -> list:
    out = []
    for e in events:
        if e["event_type"] == "synthetic_file_access" and e["attributes"].get("outcome") == "served":
            asset = str(e["attributes"].get("asset_id", "unknown"))[:128]
            out.append(finding(
                "R04", f"event={e['event_id']}",
                techniques=["T1005"], stage="data_access",
                label=f"Synthetic file served: {asset}",
                limitation="The file is synthetic; no real data was taken.",
                events=[e],
            ))
    return out
