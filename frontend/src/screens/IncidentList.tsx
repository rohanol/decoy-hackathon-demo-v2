/**
 * Screen 3 — Incident List. DESIGN_SPEC.md section 8.
 *
 * Cards rather than a dense table: this lab produces one to three incidents,
 * and cards let the kill-chain silhouette breathe. Scanning those silhouettes
 * down the page is the point — how far each source got, side by side.
 *
 * Built strictly from IncidentSummary. That shape carries no findings, and
 * `Link` carries no incident_id, so the rule chips and "awaiting decision" flag
 * from the original wireframe have no honest source here. Rather than N+1
 * fetching every incident or inventing the data, the card shows what the list
 * endpoint actually returns. See open question 2 in DESIGN_SPEC.md.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { ApiError, fetchIncidents } from '../api/client';
import { KillChainStrip } from '../components/KillChainBar';
import { EmptyState, ErrorCard, SkeletonRows } from '../components/primitives';
import { COPY } from '../copy';
import { fullUtc, number, timeUtcZ } from '../lib/format';
import { useLiveStore } from '../state/LiveStore';
import type { IncidentSummary } from '../types/api';

function duration(from: string, to: string): string {
  const seconds = Math.max(
    0,
    Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000),
  );
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}

function IncidentCard({
  incident,
  justUpdated,
}: {
  incident: IncidentSummary;
  justUpdated: boolean;
}) {
  return (
    <RouterLink
      to={`/incidents/${incident.incident_id}`}
      className={
        justUpdated
          ? `inccard inccard--${incident.severity} inccard--updated`
          : `inccard inccard--${incident.severity}`
      }
    >
      <div className="inccard__top">
        <span className={`badge badge--${incident.severity}`}>{incident.severity}</span>
        <span className={`inccard__score inccard__score--${incident.severity}`}>
          {number(incident.score)}
        </span>
        <span className="inccard__ip mono">{incident.src_ip}</span>
        <span className="inccard__count">{number(incident.event_count)} events</span>
      </div>

      <KillChainStrip stagesObserved={incident.stages_observed} severity={incident.severity} />

      <div className="inccard__meta mono">
        {incident.incident_id} · {incident.lab_run_id} · first {fullUtc(incident.first_seen)} ·
        last {timeUtcZ(incident.last_seen)} · {duration(incident.first_seen, incident.last_seen)}
      </div>
    </RouterLink>
  );
}

export function IncidentList() {
  const { subscribe } = useLiveStore();
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [updatedIds, setUpdatedIds] = useState<Set<string>>(new Set());
  const flashTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await fetchIncidents();
      setIncidents(page.items);
      setError(null);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError('incidents_load_failed', 'Could not load incidents.', 0),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Live updates: an `incident` message carries an IncidentSummary, which
  // replaces the one on screen. We display what arrived; we do not merge or
  // recompute any of its fields.
  useEffect(() => {
    const unsubscribe = subscribe((message) => {
      if (message.type !== 'incident') return;
      const summary = message.data as IncidentSummary;
      if (!summary?.incident_id) return;

      setIncidents((current) => {
        const index = current.findIndex((item) => item.incident_id === summary.incident_id);
        return index === -1
          ? [summary, ...current]
          : current.map((item) => (item.incident_id === summary.incident_id ? summary : item));
      });

      setUpdatedIds((current) => new Set(current).add(summary.incident_id));
      const timer = setTimeout(() => {
        setUpdatedIds((current) => {
          const next = new Set(current);
          next.delete(summary.incident_id);
          return next;
        });
      }, 1200);
      flashTimers.current.push(timer);
    });

    return () => {
      unsubscribe();
      for (const timer of flashTimers.current) clearTimeout(timer);
      flashTimers.current = [];
    };
  }, [subscribe]);

  /** Newest activity first. */
  const sorted = useMemo(
    () => [...incidents].sort((a, b) => b.last_seen.localeCompare(a.last_seen)),
    [incidents],
  );

  return (
    <div className="page">
      <div className="page__head">
        <h1 className="page__title">Incidents</h1>
        <span className="page__head-spacer" />
        <span className="toolbar__count">
          {number(sorted.length)} incident{sorted.length === 1 ? '' : 's'}
        </span>
      </div>

      {error && incidents.length === 0 ? (
        <ErrorCard error={error} onRetry={() => void load()} />
      ) : loading && incidents.length === 0 ? (
        <section className="card">
          <SkeletonRows rows={6} />
        </section>
      ) : sorted.length === 0 ? (
        <section className="card">
          <EmptyState title={COPY.emptyIncidentsTitle} hint={COPY.emptyIncidentsHint} />
        </section>
      ) : (
        <div className="inclist">
          {sorted.map((incident) => (
            <IncidentCard
              key={incident.incident_id}
              incident={incident}
              justUpdated={updatedIds.has(incident.incident_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
