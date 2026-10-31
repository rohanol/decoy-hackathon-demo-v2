/**
 * Finding card. DESIGN_SPEC.md section 9.4.
 *
 * The limitation line is always visible, at body size, right under the label.
 * It is never behind a tooltip or an accordion: "this is what we saw, this is
 * what it does not prove" is the project's core honesty claim
 * (AGENTS.md section 7), not a disclaimer to tuck away.
 *
 * Every evidence id is clickable through to the raw event. That is what makes
 * "evidence-linked" checkable rather than a slogan.
 */

import { useState } from 'react';
import { STAGE_LABEL } from '../copy';
import type { Finding, SocEvent } from '../types/api';

/** MITRE's canonical URL for a technique id: T1110.001 -> /techniques/T1110/001/ */
function attackUrl(techniqueId: string): string {
  const [base, sub] = techniqueId.split('.');
  return sub
    ? `https://attack.mitre.org/techniques/${base}/${sub}/`
    : `https://attack.mitre.org/techniques/${base}/`;
}

function EvidenceChips({
  eventIds,
  eventsById,
  onOpenEvent,
}: {
  eventIds: string[];
  eventsById: Map<string, SocEvent>;
  onOpenEvent: (event: SocEvent) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? eventIds : eventIds.slice(0, 3);
  const hidden = eventIds.length - visible.length;

  return (
    <div className="evidence">
      <span className="evidence__label">evidence</span>
      {visible.map((eventId) => {
        const event = eventsById.get(eventId);
        if (!event) {
          // The event is not in the window we loaded. Show the id, do not
          // pretend it is clickable.
          return (
            <span key={eventId} className="chip" title="Event not in the loaded window">
              {eventId}
            </span>
          );
        }
        return (
          <button
            key={eventId}
            type="button"
            className="chip"
            onClick={() => onOpenEvent(event)}
            title="Open the raw event"
          >
            {eventId}
          </button>
        );
      })}
      {hidden > 0 ? (
        <button type="button" className="chip" onClick={() => setExpanded(true)}>
          +{hidden}
        </button>
      ) : null}
    </div>
  );
}

export function FindingCard({
  finding,
  eventsById,
  onOpenEvent,
}: {
  finding: Finding;
  eventsById: Map<string, SocEvent>;
  onOpenEvent: (event: SocEvent) => void;
}) {
  const pending = finding.pending_confirmation === true;

  return (
    <article className={pending ? 'finding finding--pending' : 'finding'}>
      <header className="finding__head">
        <span className="finding__rule">{finding.rule_id}</span>
        {finding.stage !== 'none' ? (
          <span className="chip">{STAGE_LABEL[finding.stage]}</span>
        ) : null}
        {finding.technique_ids.map((techniqueId) => (
          <a
            key={techniqueId}
            className="chip"
            href={attackUrl(techniqueId)}
            target="_blank"
            rel="noopener noreferrer"
            title="MITRE ATT&CK technique"
          >
            {techniqueId}
          </a>
        ))}
        {finding.web_attack_class?.map((attackClass) => (
          <span key={attackClass} className="chip chip--warn" title="Matched web attack class">
            {attackClass}
          </span>
        ))}
        {pending ? <span className="chip chip--pending">⚑ pending</span> : null}
        <span className="finding__points">{finding.points ?? 0} pts</span>
      </header>

      <p className="finding__label">{finding.label}</p>
      <p className="finding__limitation">
        <span aria-hidden="true">ⓘ </span>
        {finding.limitation}
      </p>

      <EvidenceChips
        eventIds={finding.evidence_event_ids}
        eventsById={eventsById}
        onOpenEvent={onOpenEvent}
      />
    </article>
  );
}
