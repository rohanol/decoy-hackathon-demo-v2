"""R05: the analyst confirmed a cross-decoy link that touches this incident.

Unlike the other rules this one reads links, not events. Rejecting the link removes it.
"""
from ._util import finding


def evaluate(incident_id: str, links: list) -> list:
    out = []
    for link in links:
        if link["status"] != "confirmed":
            continue
        if incident_id not in (link["from_incident_id"], link["to_incident_id"]):
            continue
        out.append(finding(
            "R05", f"link={link['link_id']}",
            techniques=[], stage="none",
            label=f"Analyst-confirmed cross-decoy link {link['link_id']} ({link['from_sensor']} to {link['to_sensor']})",
            limitation="An analyst judgement; does not show that it is the same person.",
            events=[{"event_id": link["from_event_id"]}, {"event_id": link["to_event_id"]}],
        ))
    return out
