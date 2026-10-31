/**
 * The one piece of state that must never lie. DESIGN_SPEC.md section 4.3.
 *
 * When offline it reports the time data was last received, and clicking it
 * forces an immediate retry instead of waiting out the backoff.
 */

import { Dot } from './primitives';
import { timeUtcZ } from '../lib/format';
import { useLiveStore } from '../state/LiveStore';

export function ConnectionPill() {
  const { status, lastDataAt, retryNow } = useLiveStore();

  if (status.state === 'live') {
    return (
      <span className="pill pill--ok" title="Receiving events over /ws/events">
        <Dot tone="ok" animate="pulse" />
        live
      </span>
    );
  }

  if (status.state === 'connecting') {
    return (
      <span className="pill" title="Opening the event stream">
        <Dot tone="neutral" />
        connecting
      </span>
    );
  }

  if (status.state === 'reconnecting') {
    return (
      <span className="pill pill--warn" title="The event stream dropped. Retrying with backoff.">
        <Dot tone="warn" animate="blink" />
        reconnecting · attempt {status.attempt}
      </span>
    );
  }

  const since = lastDataAt ? timeUtcZ(lastDataAt.toISOString()) : 'never';
  return (
    <button
      type="button"
      className="pill pill--danger"
      onClick={retryNow}
      title="Click to retry now"
    >
      <Dot tone="danger" />
      offline — showing data from {since}
    </button>
  );
}
