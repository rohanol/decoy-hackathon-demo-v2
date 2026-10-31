/**
 * Screen 2 — Live Feed. DESIGN_SPEC.md section 7.
 *
 * This is the H4 gate: a real SSH event from Kali, visible here, with its event
 * ID (AGENTS.md section 5, M1_frontend.md task 1).
 */

import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorCard, SkeletonRows, AttackerText } from '../components/primitives';
import { RawEventDrawer } from '../components/RawEventDrawer';
import { COPY, EVENT_TYPE_LABEL } from '../copy';
import { FEED_MAX_ROWS } from '../api/config';
import { EVENT_STYLE } from '../lib/eventStyle';
import { bytes, clamp, number, timeUtc } from '../lib/format';
import { useLiveStore } from '../state/LiveStore';
import { EVENT_TYPES, SENSOR_IDS, type EventType, type SocEvent } from '../types/api';

const DETAIL_MAX = 60;

/** One or two lines derived from attributes. DESIGN_SPEC.md section 7.3. */
function DetailCell({ event }: { event: SocEvent }) {
  const attributes = event.attributes ?? {};

  switch (event.event_type) {
    case 'auth_failure':
    case 'auth_success':
      return attributes.username ? (
        <AttackerText value={`username=${clamp(attributes.username, DETAIL_MAX)}`} />
      ) : null;

    case 'command_input':
      return attributes.command ? (
        <AttackerText value={clamp(attributes.command, DETAIL_MAX)} />
      ) : null;

    case 'http_request':
    case 'blocked_request': {
      const line = `${attributes.method ?? ''} ${attributes.path ?? ''}`.trim();
      return (
        <>
          {line ? <AttackerText value={clamp(line, DETAIL_MAX)} /> : null}
          {attributes.query_redacted ? (
            <AttackerText value={clamp(attributes.query_redacted, DETAIL_MAX)} />
          ) : null}
          {event.event_type === 'blocked_request' && attributes.block_action_id ? (
            <span className="mono">{attributes.block_action_id}</span>
          ) : null}
        </>
      );
    }

    case 'synthetic_file_access':
      return (
        <>
          {attributes.asset_id ? (
            <AttackerText value={clamp(attributes.asset_id, DETAIL_MAX)} />
          ) : null}
          {typeof attributes.size_bytes === 'number' ? (
            <span className="mono">{bytes(attributes.size_bytes)}</span>
          ) : null}
        </>
      );

    case 'connection_open':
      return attributes.client_version ? (
        <AttackerText value={clamp(attributes.client_version, DETAIL_MAX)} />
      ) : null;

    default:
      return null;
  }
}

/** Status / outcome line under the event type. */
function eventSubLabel(event: SocEvent): string | null {
  const attributes = event.attributes ?? {};
  const parts: string[] = [];
  if (typeof attributes.status_code === 'number') parts.push(String(attributes.status_code));
  if (attributes.response_class) parts.push(attributes.response_class);
  if (attributes.outcome) parts.push(attributes.outcome);
  return parts.length > 0 ? parts.join(' ') : null;
}

function EventRow({
  event,
  isLive,
  isSelected,
  onSelect,
}: {
  event: SocEvent;
  isLive: boolean;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const style = EVENT_STYLE[event.event_type];
  const sub = eventSubLabel(event);

  const classes = ['', isLive ? 'row--new' : '', isSelected ? 'is-selected' : '']
    .filter(Boolean)
    .join(' ');

  return (
    <tr
      className={classes}
      onClick={onSelect}
      tabIndex={0}
      onKeyDown={(keyEvent) => {
        if (keyEvent.key === 'Enter' || keyEvent.key === ' ') {
          keyEvent.preventDefault();
          onSelect();
        }
      }}
    >
      <td className="cell-time">{timeUtc(event.occurred_at)}</td>
      <td className="cell-sensor">{event.sensor_id}</td>
      <td>
        <div className={`evtype evtype--${style.tone}`}>
          <span className="evtype__glyph">{style.glyph}</span>
          <span className="evtype__label">{EVENT_TYPE_LABEL[event.event_type]}</span>
        </div>
        {sub ? <div className="evtype__sub">{sub}</div> : null}
      </td>
      <td className="mono">{event.src_ip}</td>
      <td>
        <div className="cell-detail">
          <DetailCell event={event} />
          <div className="cell-detail__ids">
            <span>{event.event_id}</span>
            {event.incident_id ? (
              <Link
                to={`/incidents/${event.incident_id}`}
                onClick={(clickEvent) => clickEvent.stopPropagation()}
              >
                {event.incident_id}
              </Link>
            ) : null}
          </div>
        </div>
      </td>
    </tr>
  );
}

export function LiveFeed() {
  const {
    events,
    receivedCount,
    snapshotMaxSeq,
    paused,
    bufferedCount,
    loading,
    error,
    setPaused,
    reload,
  } = useLiveStore();

  const [sensorFilter, setSensorFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [ipFilter, setIpFilter] = useState<string>('');
  const [selected, setSelected] = useState<SocEvent | null>(null);

  const filtered = useMemo(() => {
    const ip = ipFilter.trim();
    return events.filter((event) => {
      if (sensorFilter && event.sensor_id !== sensorFilter) return false;
      if (typeFilter && event.event_type !== typeFilter) return false;
      if (ip && !event.src_ip.includes(ip)) return false;
      return true;
    });
  }, [events, sensorFilter, typeFilter, ipFilter]);

  const filtersActive = sensorFilter !== '' || typeFilter !== '' || ipFilter.trim() !== '';
  const trimmed = receivedCount > FEED_MAX_ROWS;

  return (
    <div className="page">
      <div className="page__head">
        <h1 className="page__title">Live Feed</h1>
        <span className="page__head-spacer" />
        {paused ? (
          <span className="pill pill--warn">paused · {bufferedCount} new</span>
        ) : null}
        <button type="button" className="btn" onClick={() => setPaused(!paused)}>
          {paused ? 'Resume' : 'Pause'}
        </button>
      </div>

      <div className="toolbar">
        <select
          className="select"
          aria-label="Filter by sensor"
          value={sensorFilter}
          onChange={(changeEvent) => setSensorFilter(changeEvent.target.value)}
        >
          <option value="">All sensors</option>
          {SENSOR_IDS.map((sensorId) => (
            <option key={sensorId} value={sensorId}>
              {sensorId}
            </option>
          ))}
        </select>

        <select
          className="select"
          aria-label="Filter by event type"
          value={typeFilter}
          onChange={(changeEvent) => setTypeFilter(changeEvent.target.value)}
        >
          <option value="">All event types</option>
          {EVENT_TYPES.map((eventType: EventType) => (
            <option key={eventType} value={eventType}>
              {EVENT_TYPE_LABEL[eventType]}
            </option>
          ))}
        </select>

        <input
          className="input"
          aria-label="Filter by source IP"
          placeholder="src_ip"
          value={ipFilter}
          onChange={(changeEvent) => setIpFilter(changeEvent.target.value)}
        />

        <span className="toolbar__spacer" />
        <span className="toolbar__count">
          {number(filtered.length)}
          {filtersActive ? ` of ${number(events.length)}` : ''} events
        </span>
      </div>

      {/* Never let a filtered view be mistaken for the whole truth. */}
      {filtersActive ? (
        <div className="filternote">
          Filtered view — {number(events.length - filtered.length)} loaded events hidden.{' '}
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setSensorFilter('');
              setTypeFilter('');
              setIpFilter('');
            }}
          >
            Clear filters
          </button>
        </div>
      ) : null}

      <section className="card">
        {error ? (
          <div style={{ padding: 'var(--s4)' }}>
            <ErrorCard error={error} onRetry={reload} />
          </div>
        ) : loading && events.length === 0 ? (
          <SkeletonRows rows={8} />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={filtersActive ? 'No events match these filters.' : COPY.emptyFeedTitle}
            hint={
              filtersActive
                ? 'Clear the filters to see everything that has arrived.'
                : COPY.emptyFeedHint
            }
          />
        ) : (
          <>
            <table className="feed">
              <thead>
                <tr>
                  <th className="feed__col-time" scope="col">
                    Time UTC
                  </th>
                  <th className="feed__col-sensor" scope="col">
                    Sensor
                  </th>
                  <th className="feed__col-event" scope="col">
                    Event
                  </th>
                  <th className="feed__col-source" scope="col">
                    Source
                  </th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((event) => (
                  <EventRow
                    key={event.event_id}
                    event={event}
                    isLive={event.seq > snapshotMaxSeq}
                    isSelected={selected?.event_id === event.event_id}
                    onSelect={() => setSelected(event)}
                  />
                ))}
              </tbody>
            </table>
            {trimmed ? (
              <div className="feed__footer">
                showing newest {number(events.length)} of {number(receivedCount)} received
              </div>
            ) : null}
          </>
        )}
      </section>

      {selected ? (
        <RawEventDrawer event={selected} onClose={() => setSelected(null)} />
      ) : null}
    </div>
  );
}
