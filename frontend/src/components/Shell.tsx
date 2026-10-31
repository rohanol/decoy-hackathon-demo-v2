/** App shell: topbar, sidebar, sensor health strip. DESIGN_SPEC.md section 4. */

import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { ConnectionPill } from './ConnectionPill';
import { Dot } from './primitives';
import { USE_FIXTURES } from '../api/config';
import { SENSOR_LABEL } from '../copy';
import { relativeFromNow } from '../lib/format';
import { useLiveStore } from '../state/LiveStore';
import { SENSOR_IDS } from '../types/api';

/**
 * LIVE / REPLAY / FIXTURES, on every screen (PRD section 8).
 *
 * Two independent signals guard the demo path: the build-time fixture flag, and
 * capture_mode on the events themselves. Fixture events carry
 * capture_mode "replay", so even if the flag check were bypassed the chip would
 * still not read LIVE.
 */
function CaptureChip() {
  const { captureMode } = useLiveStore();

  if (USE_FIXTURES) {
    return (
      <span
        className="pill pill--warn"
        title="Fixture data from contracts/examples/events_p3.json. Not a live capture."
      >
        FIXTURES
      </span>
    );
  }
  if (captureMode === 'replay') {
    return (
      <span className="pill pill--pending" title="Replayed capture, not live sensor traffic">
        REPLAY
      </span>
    );
  }
  if (captureMode === null) {
    // No events yet, so there is no capture to describe. Claiming LIVE here
    // would be a claim we cannot back (DESIGN_SPEC.md law 3).
    return (
      <span className="pill" title="No events received yet, so there is no capture mode to report">
        NO DATA
      </span>
    );
  }
  return (
    <span className="pill pill--ok" title="Live sensor traffic">
      LIVE
    </span>
  );
}

function UtcClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <span className="topbar__clock" title="All timestamps in this app are UTC">
      {now.toISOString().slice(11, 19)} UTC
    </span>
  );
}

/**
 * The cheapest insurance in the build: when the demo misbehaves this says
 * instantly whether the problem is the decoy, the backend or the UI.
 */
function SensorHealthStrip() {
  const { health } = useLiveStore();
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <>
      <div className="sidebar__divider" />
      <div className="sidebar__section">
        <span className="label">Sensors</span>
      </div>
      {SENSOR_IDS.map((sensorId) => {
        if (health === null) {
          return (
            <div className="sensorrow" key={sensorId}>
              <Dot tone="danger" />
              <span className="sensorrow__name">{sensorId}</span>
              <span className="sensorrow__when">unreachable</span>
            </div>
          );
        }

        const lastSeen = health.sensors[sensorId] ?? null;
        if (lastSeen === null) {
          return (
            <div className="sensorrow" key={sensorId}>
              <Dot tone="neutral" />
              <span className="sensorrow__name">{sensorId}</span>
              <span className="sensorrow__when">no events yet</span>
            </div>
          );
        }

        const ageSeconds = Math.max(0, (now.getTime() - new Date(lastSeen).getTime()) / 1000);
        const tone = ageSeconds < 60 ? 'ok' : ageSeconds < 300 ? 'warn' : 'neutral';
        return (
          <div className="sensorrow" key={sensorId} title={SENSOR_LABEL[sensorId] ?? sensorId}>
            <Dot tone={tone} />
            <span className="sensorrow__name">{sensorId}</span>
            <span className="sensorrow__when">
              {tone === 'warn' ? 'stale · ' : ''}
              {relativeFromNow(lastSeen, now)}
            </span>
          </div>
        );
      })}
    </>
  );
}

const NAV = [
  { to: '/', label: 'Overview', end: true },
  { to: '/events', label: 'Live Feed', end: false },
  { to: '/incidents', label: 'Incidents', end: false },
  { to: '/graph', label: 'Attack Graph', end: false },
  { to: '/response', label: 'Response', end: false },
] as const;

export function Shell() {
  const { labRunId, receivedCount } = useLiveStore();

  return (
    <div className="shell">
      <header className="topbar">
        <span className="topbar__brand">DeceptionGraph SOC</span>
        <CaptureChip />
        <span className="topbar__spacer" />
        {labRunId ? (
          <span className="topbar__run" title="lab_run_id">
            {labRunId}
          </span>
        ) : null}
        <ConnectionPill />
        <UtcClock />
      </header>

      <nav className="sidebar">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => (isActive ? 'navitem navitem--active' : 'navitem')}
          >
            {item.label}
            {item.to === '/events' && receivedCount > 0 ? (
              <span className="navitem__count">{receivedCount}</span>
            ) : null}
          </NavLink>
        ))}
        <SensorHealthStrip />
      </nav>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
