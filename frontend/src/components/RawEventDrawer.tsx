/**
 * Raw event drawer. DESIGN_SPEC.md section 7.4.
 *
 * Every field of the event, exactly as the API returned it. This is what makes
 * "evidence-linked" a real claim rather than a slogan: any ID on any screen can
 * be opened here and checked.
 */

import { useEffect, useRef } from 'react';
import { AttackerText, CopyableValue } from './primitives';
import { EVENT_TYPE_DESCRIPTION, EVENT_TYPE_LABEL, SENSOR_LABEL } from '../copy';
import { EVENT_STYLE } from '../lib/eventStyle';
import { bytes, fullUtc, shortHash } from '../lib/format';
import type { SocEvent } from '../types/api';

/** Attacker-controlled attributes get the bounded well treatment. */
const HOSTILE_KEYS = new Set(['command', 'path', 'query_redacted', 'user_agent', 'username']);

/** Hashes are shown truncated with a copy button, never raw in a table. */
const HASH_KEYS = new Set(['password_sha256', 'sha256']);

function AttributeValue({ attrKey, value }: { attrKey: string; value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="kv__v kv__v--muted">null</span>;
  }
  if (HASH_KEYS.has(attrKey) && typeof value === 'string') {
    return (
      <span className="kv__v">
        <CopyableValue value={value} display={shortHash(value)} />
      </span>
    );
  }
  if (HOSTILE_KEYS.has(attrKey) && typeof value === 'string') {
    return (
      <span className="kv__v">
        <AttackerText value={value} well />
      </span>
    );
  }
  if (attrKey === 'size_bytes' && typeof value === 'number') {
    return <span className="kv__v">{bytes(value)}</span>;
  }
  if (typeof value === 'object') {
    return <span className="kv__v">{JSON.stringify(value)}</span>;
  }
  return <span className="kv__v">{String(value)}</span>;
}

export function RawEventDrawer({ event, onClose }: { event: SocEvent; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (keyEvent: KeyboardEvent) => {
      if (keyEvent.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const style = EVENT_STYLE[event.event_type];
  const attributes = Object.entries(event.attributes ?? {});

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="drawer" role="dialog" aria-label="Raw event" aria-modal="true">
        <header className="drawer__head">
          <div className="drawer__title">
            <span className={`evtype evtype--${style.tone}`}>
              <span className="evtype__glyph">{style.glyph}</span>
            </span>
            <span>{EVENT_TYPE_LABEL[event.event_type]}</span>
            <button
              ref={closeRef}
              type="button"
              className="btn btn--ghost drawer__close"
              onClick={onClose}
            >
              Close
            </button>
          </div>
          <div className="drawer__note">{EVENT_TYPE_DESCRIPTION[event.event_type]}</div>
          <CopyableValue value={event.event_id} />
        </header>

        <div className="drawer__body">
          <section>
            <div className="drawer__section-title">Event</div>
            <div className="kv">
              <span className="kv__k">event_id</span>
              <span className="kv__v">{event.event_id}</span>
              <span className="kv__k">seq</span>
              <span className="kv__v">{event.seq}</span>
              <span className="kv__k">sensor_id</span>
              <span className="kv__v">
                {event.sensor_id}
                <span className="drawer__note"> {SENSOR_LABEL[event.sensor_id] ?? ''}</span>
              </span>
              <span className="kv__k">event_type</span>
              <span className="kv__v">{event.event_type}</span>
              <span className="kv__k">occurred_at</span>
              <span className="kv__v">{fullUtc(event.occurred_at)}</span>
              <span className="kv__k">ingested_at</span>
              <span className="kv__v">{fullUtc(event.ingested_at)}</span>
              <span className="kv__k">src_ip</span>
              <span className="kv__v">{event.src_ip}</span>
              <span className="kv__k">src_port</span>
              <span className={event.src_port == null ? 'kv__v kv__v--muted' : 'kv__v'}>
                {event.src_port ?? 'null'}
              </span>
              <span className="kv__k">session_id</span>
              <span className={event.session_id == null ? 'kv__v kv__v--muted' : 'kv__v'}>
                {event.session_id ?? 'null'}
              </span>
              <span className="kv__k">incident_id</span>
              <span className={event.incident_id == null ? 'kv__v kv__v--muted' : 'kv__v'}>
                {event.incident_id ?? 'null'}
              </span>
              <span className="kv__k">lab_run_id</span>
              <span className="kv__v">{event.lab_run_id}</span>
              <span className="kv__k">capture_mode</span>
              <span className="kv__v">{event.capture_mode}</span>
              <span className="kv__k">schema_version</span>
              <span className="kv__v">{event.schema_version}</span>
              <span className="kv__k">source_record_id</span>
              <span className="kv__v">
                <CopyableValue
                  value={event.source_record_id}
                  display={shortHash(event.source_record_id)}
                />
              </span>
            </div>
          </section>

          <section>
            <div className="drawer__section-title">Attributes</div>
            {attributes.length === 0 ? (
              <div className="drawer__note">No attributes on this event.</div>
            ) : (
              <div className="kv">
                {attributes.map(([key, value]) => (
                  <span key={key} style={{ display: 'contents' }}>
                    <span className="kv__k">{key}</span>
                    <AttributeValue attrKey={key} value={value} />
                  </span>
                ))}
              </div>
            )}
          </section>
        </div>
      </aside>
    </>
  );
}
