/**
 * Link decision modal. DESIGN_SPEC.md section 11.3.
 *
 * The analyst is making a judgement call, so the evidence sits on the same
 * surface as the decision. The rationale is mandatory and recorded.
 *
 * Deliberate restraint: the wording states the consequence of confirming, it
 * does not recommend confirming. The UI must not nudge the analyst toward the
 * answer that makes the demo look better.
 */

import { useEffect, useRef, useState } from 'react';
import { ApiError, postLinkDecision } from '../api/client';
import { AttackerText, ErrorCard } from './primitives';
import { COPY, SENSOR_LABEL, linkPhrase } from '../copy';
import { timeUtcZ } from '../lib/format';
import type { Link, SocEvent } from '../types/api';

const MIN_RATIONALE = 5;

/** A one-line description of an evidence event, for the modal only. */
function evidenceDetail(event: SocEvent): string {
  const attributes = event.attributes ?? {};
  if (attributes.command) return attributes.command;
  if (attributes.path) {
    const method = attributes.method ? `${attributes.method} ` : '';
    return `${method}${attributes.path}${attributes.username ? ` (${attributes.username})` : ''}`;
  }
  if (attributes.asset_id) return attributes.asset_id;
  if (attributes.username) return `username=${attributes.username}`;
  return event.event_type;
}

function EvidenceRow({
  role,
  eventId,
  event,
}: {
  role: string;
  eventId: string;
  event: SocEvent | undefined;
}) {
  return (
    <div className="evrow">
      <span className="evrow__role">{role}</span>
      <span className="evrow__id mono">{eventId}</span>
      <span className="evrow__time mono">{event ? timeUtcZ(event.occurred_at) : '—'}</span>
      <span className="evrow__detail">
        {event ? (
          <AttackerText value={evidenceDetail(event)} />
        ) : (
          <span className="state__hint">not in the loaded window</span>
        )}
      </span>
    </div>
  );
}

export function LinkDecisionModal({
  link,
  eventsById,
  onClose,
  onDecided,
}: {
  link: Link;
  eventsById: Map<string, SocEvent>;
  onClose: () => void;
  onDecided: () => void;
}) {
  const [rationale, setRationale] = useState(link.rationale ?? '');
  const [saving, setSaving] = useState<'confirm' | 'reject' | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
    const onKeyDown = (keyEvent: KeyboardEvent) => {
      if (keyEvent.key === 'Escape' && saving === null) onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose, saving]);

  const tooShort = rationale.trim().length < MIN_RATIONALE;
  const busy = saving !== null;
  const alreadyDecided = link.status !== 'open';

  async function decide(decision: 'confirm' | 'reject') {
    setSaving(decision);
    setError(null);
    try {
      await postLinkDecision(link.link_id, decision, rationale.trim());
      // Do not restyle anything locally: reload from the API so what is on
      // screen is what the backend actually recorded (law 1).
      onDecided();
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError('decision_failed', 'The decision was not recorded.', 0),
      );
      setSaving(null);
    }
  }

  return (
    <>
      <div className="modal-backdrop" onClick={busy ? undefined : onClose} aria-hidden="true" />
      <div className="modal" role="dialog" aria-modal="true" aria-label="Cross-decoy link decision">
        <header className="modal__head">
          <h2 className="modal__title">
            {alreadyDecided ? 'Change link decision' : 'Confirm cross-decoy link'}
          </h2>
        </header>

        <div className="modal__body">
          <div className="linkhead">
            <span className="mono">{link.from_sensor}</span>
            <span className="linkhead__arrow">⇢</span>
            <span className="mono">{link.to_sensor}</span>
          </div>
          <div className="modal__meta">
            {SENSOR_LABEL[link.from_sensor]} to {SENSOR_LABEL[link.to_sensor]} ·{' '}
            {linkPhrase(link.kind, link.status)}
          </div>
          <div className="kv">
            <span className="kv__k">basis</span>
            <span className="kv__v">{link.basis}</span>
            <span className="kv__k">link_id</span>
            <span className="kv__v">{link.link_id}</span>
          </div>

          <section>
            <div className="drawer__section-title">Evidence</div>
            <EvidenceRow
              role="from"
              eventId={link.from_event_id}
              event={eventsById.get(link.from_event_id)}
            />
            <EvidenceRow
              role="to"
              eventId={link.to_event_id}
              event={eventsById.get(link.to_event_id)}
            />
          </section>

          <p className="modal__consequence">
            Confirming makes R05 count
            {link.kind === 'strong_candidate'
              ? ', and R09 as well because this is a strong candidate'
              : ''}
            . The backend recalculates the score.
          </p>

          <label className="field">
            <span className="label">
              Rationale (required, min {MIN_RATIONALE} characters)
            </span>
            <textarea
              ref={textareaRef}
              className="textarea"
              rows={3}
              value={rationale}
              disabled={busy}
              onChange={(changeEvent) => setRationale(changeEvent.target.value)}
            />
            <span className={tooShort ? 'field__count field__count--short' : 'field__count'}>
              {rationale.trim().length} / {MIN_RATIONALE}
            </span>
          </label>

          <p className="modal__caveat">{COPY.linkCaveat}</p>

          {error ? <ErrorCard error={error} /> : null}
        </div>

        <footer className="modal__foot">
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <span className="toolbar__spacer" />
          <button
            type="button"
            className="btn"
            disabled={tooShort || busy}
            onClick={() => void decide('reject')}
          >
            {saving === 'reject' ? 'Rejecting…' : 'Reject'}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={tooShort || busy}
            onClick={() => void decide('confirm')}
          >
            {saving === 'confirm' ? 'Confirming…' : 'Confirm link'}
          </button>
        </footer>
      </div>
    </>
  );
}
