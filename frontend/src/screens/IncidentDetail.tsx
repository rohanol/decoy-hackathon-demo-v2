/**
 * Screen 4 — Incident Detail. DESIGN_SPEC.md section 9.
 *
 * The screen that is on the projector for most of the demo. Two columns:
 * evidence on the left, machinery on the right.
 *
 * Law 1 throughout: score, severity, stages, points and link status are all
 * displayed exactly as the API reported them. The only arithmetic here is the
 * raw sum in the score breakdown, which is labelled "raw" and sits next to the
 * cap note rather than replacing the real score.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { ApiError, fetchEvents, fetchIncident, incidentExportUrl } from '../api/client';
import { USE_FIXTURES } from '../api/config';
import { FindingCard } from '../components/FindingCard';
import { KillChainBar } from '../components/KillChainBar';
import { LinkDecisionModal } from '../components/LinkDecisionModal';
import { RawEventDrawer } from '../components/RawEventDrawer';
import { ScoreBreakdown } from '../components/ScoreBreakdown';
import { Card, EmptyState, ErrorCard, SkeletonRows } from '../components/primitives';
import { STAGE_LABEL, linkPhrase } from '../copy';
import { fullUtc, number, timeUtcZ } from '../lib/format';
import type { Incident, Link, SocEvent, Stage } from '../types/api';

/** "2m 30s" between two timestamps. Presentation only. */
function duration(from: string, to: string): string {
  const seconds = Math.max(0, Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000));
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}

function LinkRow({ link, onDecide }: { link: Link; onDecide: (link: Link) => void }) {
  const classes = [
    'linkrow',
    `linkrow--${link.status}`,
    link.status === 'open' && link.kind === 'strong_candidate' ? 'linkrow--strong' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes}>
      <div className="linkrow__sensors">
        <span className="mono">{link.from_sensor}</span>
        <span className="linkhead__arrow">⇢</span>
        <span className="mono">{link.to_sensor}</span>
      </div>
      <div className="linkrow__phrase">{linkPhrase(link.kind, link.status)}</div>
      <div className="linkrow__basis mono">{link.basis}</div>
      {link.rationale ? (
        <div className="linkrow__rationale">
          “{link.rationale}”
          {link.decided_at ? <span className="mono"> {timeUtcZ(link.decided_at)}</span> : null}
        </div>
      ) : null}
      <div className="linkrow__actions">
        <button type="button" className="btn" onClick={() => onDecide(link)}>
          {link.status === 'open' ? 'Confirm or reject' : 'Change decision'}
        </button>
      </div>
    </div>
  );
}

export function IncidentDetail() {
  const { incidentId } = useParams<{ incidentId: string }>();

  const [incident, setIncident] = useState<Incident | null>(null);
  const [eventsById, setEventsById] = useState<Map<string, SocEvent>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const [stageFilter, setStageFilter] = useState<Stage | null>(null);
  const [openEvent, setOpenEvent] = useState<SocEvent | null>(null);
  const [decidingLink, setDecidingLink] = useState<Link | null>(null);

  const load = useCallback(async () => {
    if (!incidentId) return;
    setLoading(true);
    try {
      // The incident drives the page; the events are fetched alongside it so
      // every evidence id on screen can open its raw event.
      const [loadedIncident, eventsPage] = await Promise.all([
        fetchIncident(incidentId),
        fetchEvents({ incident_id: incidentId, limit: 200 }),
      ]);
      setIncident(loadedIncident);
      setEventsById(new Map(eventsPage.items.map((event) => [event.event_id, event])));
      setError(null);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError('incident_load_failed', 'Could not load this incident.', 0),
      );
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleFindings = useMemo(() => {
    if (!incident) return [];
    if (stageFilter === null) return incident.findings;
    return incident.findings.filter((finding) => finding.stage === stageFilter);
  }, [incident, stageFilter]);

  if (loading && incident === null) {
    return (
      <div className="page">
        <section className="card">
          <SkeletonRows rows={10} />
        </section>
      </div>
    );
  }

  if (error && incident === null) {
    return (
      <div className="page">
        <div className="page__head">
          <RouterLink to="/incidents" className="btn btn--ghost">
            ← Incidents
          </RouterLink>
        </div>
        <ErrorCard error={error} onRetry={() => void load()} />
      </div>
    );
  }

  if (!incident) return null;


  return (
    <div className="page">
      <div className="page__head">
        <RouterLink to="/incidents" className="btn btn--ghost">
          ← Incidents
        </RouterLink>
        <span className="page__head-spacer" />
        <a
          className={USE_FIXTURES ? 'btn btn--disabled' : 'btn'}
          href={USE_FIXTURES ? undefined : incidentExportUrl(incident.incident_id)}
          title={
            USE_FIXTURES
              ? 'Export needs the live backend'
              : 'JSON export, password hashes excluded.'
          }
          aria-disabled={USE_FIXTURES}
        >
          Export
        </a>
        <button
          type="button"
          className="btn"
          disabled
          title="Response router not built yet — build order 7 of 7, needs M2"
        >
          Block
        </button>
      </div>

      <header className="inchead">
        <div className="inchead__left">
          <h1 className="inchead__ip mono">{incident.src_ip}</h1>
          <div className="inchead__meta mono">
            {incident.incident_id} · {incident.lab_run_id} ·{' '}
            {number(incident.event_count)} events · {fullUtc(incident.first_seen)} →{' '}
            {timeUtcZ(incident.last_seen)} · {duration(incident.first_seen, incident.last_seen)}
          </div>
        </div>
        <div className="inchead__right">
          <span className={`badge badge--${incident.severity}`}>{incident.severity}</span>
          <div className={`inchead__score inchead__score--${incident.severity}`}>
            {number(incident.score)}
          </div>
        </div>
      </header>

      <Card title="Kill chain">
        <div className="card__body">
          <KillChainBar
            stagesObserved={incident.stages_observed}
            findings={incident.findings}
            severity={incident.severity}
            activeStage={stageFilter}
            onStageClick={(stage) => setStageFilter((current) => (current === stage ? null : stage))}
          />
        </div>
      </Card>

      <div className="incgrid">
        <div className="incgrid__col">
          <Card title="Summary">
            <div className="card__body">
              <div className="summary__source">
                <span className="chip">{incident.summary.source}</span>
                {incident.summary.source !== 'rules' ? (
                  <span className="state__hint">
                    Generated text — all claims cite the event IDs below.
                  </span>
                ) : null}
              </div>
              <p className="summary__text">{incident.summary.text}</p>
              <div className="evidence">
                <span className="evidence__label">cited</span>
                {incident.summary.cited_event_ids.map((eventId) => {
                  const event = eventsById.get(eventId);
                  return event ? (
                    <button
                      key={eventId}
                      type="button"
                      className="chip"
                      onClick={() => setOpenEvent(event)}
                    >
                      {eventId}
                    </button>
                  ) : (
                    <span key={eventId} className="chip">
                      {eventId}
                    </span>
                  );
                })}
              </div>
            </div>
          </Card>

          <Card
            title={`Findings (${visibleFindings.length}${
              stageFilter ? ` of ${incident.findings.length}` : ''
            })`}
            actions={
              stageFilter ? (
                <button type="button" className="btn btn--ghost" onClick={() => setStageFilter(null)}>
                  Clear {STAGE_LABEL[stageFilter]} filter
                </button>
              ) : null
            }
          >
            <div className="card__body findings">
              {visibleFindings.length === 0 ? (
                <EmptyState
                  title="No findings for this stage."
                  hint="Clear the filter to see every finding on this incident."
                />
              ) : (
                visibleFindings.map((finding) => (
                  <FindingCard
                    key={finding.finding_id}
                    finding={finding}
                    eventsById={eventsById}
                    onOpenEvent={setOpenEvent}
                  />
                ))
              )}
            </div>
          </Card>
        </div>

        <div className="incgrid__col">
          <Card title="Score breakdown">
            <div className="card__body">
              <ScoreBreakdown rows={incident.score_breakdown} score={incident.score} />
            </div>
          </Card>

          <Card title={`Cross-decoy links (${incident.links.length})`}>
            <div className="card__body">
              {incident.links.length === 0 ? (
                <EmptyState
                  title="No cross-decoy links."
                  hint="A link appears when the same source touches both decoys within 5 minutes."
                />
              ) : (
                incident.links.map((link) => (
                  <LinkRow key={link.link_id} link={link} onDecide={setDecidingLink} />
                ))
              )}
            </div>
          </Card>

          <Card title={`Sessions (${incident.sessions.length})`}>
            <div className="card__body">
              {incident.sessions.length === 0 ? (
                <EmptyState
                  title="No sessions."
                  hint="SSH sessions appear here once a connection is opened."
                />
              ) : (
                <>
                  {incident.sessions.map((session) => (
                    <div
                      key={session.session_id}
                      className={
                        session.commands > 0 ? 'sessionrow' : 'sessionrow sessionrow--empty'
                      }
                    >
                      <span className="mono">{session.session_id}</span>
                      <span className="sessionrow__sensor mono">{session.sensor_id}</span>
                      <span className="sessionrow__count">
                        {session.commands} cmd{session.commands === 1 ? '' : 's'}
                      </span>
                      {session.commands > 0 ? (
                        <RouterLink
                          className="btn btn--ghost"
                          to={`/incidents/${incident.incident_id}/transcript/${session.session_id}`}
                        >
                          ▸ Replay
                        </RouterLink>
                      ) : null}
                    </div>
                  ))}
                  <p className="state__hint" style={{ textAlign: 'left', marginTop: 'var(--s2)' }}>
                    Sessions with no commands never reached a shell, so there is nothing to replay.
                  </p>
                </>
              )}
            </div>
          </Card>

          <Card title="Response">
            <div className="card__body">
              {incident.active_block === null ? (
                <p className="state__hint" style={{ textAlign: 'left' }}>
                  No action applied.
                </p>
              ) : (
                <div className="kv">
                  <span className="kv__k">action_id</span>
                  <span className="kv__v">{incident.active_block.action_id}</span>
                  <span className="kv__k">status</span>
                  <span className="kv__v">{incident.active_block.status}</span>
                  <span className="kv__k">until</span>
                  <span className="kv__v">{timeUtcZ(incident.active_block.until)}</span>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {openEvent ? (
        <RawEventDrawer event={openEvent} onClose={() => setOpenEvent(null)} />
      ) : null}

      {decidingLink ? (
        <LinkDecisionModal
          link={decidingLink}
          eventsById={eventsById}
          onClose={() => setDecidingLink(null)}
          onDecided={() => {
            setDecidingLink(null);
            void load();
          }}
        />
      ) : null}
    </div>
  );
}
