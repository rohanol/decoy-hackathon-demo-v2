"""Deterministic summaries cite findings without overstating what was observed."""

LABELS = {
    "R01": "Repeated SSH password guessing was observed",
    "R02": "A command was submitted to an emulated shell",
    "R03": "A file discovery attempt was observed",
    "R04": "A synthetic file was served; this does not show real data was stolen",
    "R05": "An analyst confirmed a cross-decoy link; this does not identify a person",
    "R07": "A web attack attempt was observed; successful exploitation is not established",
    "R08": "Repeated web path probing was observed",
    "R09": "A planted honeytoken was presented on another sensor; this does not identify a person",
}


def summarise(incident):
    sentences, cited = [], []
    for finding in incident.get("findings", []):
        rule = finding.get("rule_id")
        ids = list(dict.fromkeys(finding.get("evidence_event_ids", [])))
        if rule not in LABELS or not ids:
            continue
        text = LABELS[rule]
        if rule in {"R05", "R09"} and finding.get("pending_confirmation", False):
            text = ("A candidate link awaits analyst confirmation" if rule == "R05" else
                    "A planted honeytoken was presented on another sensor; the candidate link awaits analyst confirmation")
        sentences.append(f"{text} [evidence: {', '.join(ids)}].")
        cited.extend(event_id for event_id in ids if event_id not in cited)
    return {
        "source": "rules",
        "text": " ".join(sentences) or "No evidence-linked findings are available yet.",
        "cited_event_ids": cited,
    }
