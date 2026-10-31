/**
 * The live event store: REST snapshot plus /ws/events, shared by the shell and
 * the live feed.
 *
 * Rules it enforces (API.md, DESIGN_SPEC.md sections 4.3 and 7.1):
 *  - apply a WebSocket message only when its seq exceeds the highest seq seen
 *  - on every (re)connection, reload the REST snapshot and discard the list
 *    rather than trying to patch the gap
 *  - pausing freezes rendering only; the buffer keeps filling
 *  - the rendered list is capped, and the footer says so
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { ApiError, fetchEvents, fetchHealth } from '../api/client';
import { createEventStream, type ConnectionStatus, type EventStream } from '../api/socket';
import { EVENTS_PAGE_LIMIT, FEED_MAX_ROWS } from '../api/config';
import type { CaptureMode, Health, SocEvent, WsMessage } from '../types/api';

interface LiveStoreValue {
  /** Newest first, capped at FEED_MAX_ROWS. */
  events: SocEvent[];
  /** Total events this session has applied, including ones trimmed from the list. */
  receivedCount: number;
  /** Highest seq in the initial snapshot; rows above it arrived live and flash. */
  snapshotMaxSeq: number;
  status: ConnectionStatus;
  paused: boolean;
  bufferedCount: number;
  loading: boolean;
  error: ApiError | null;
  health: Health | null;
  /** 'replay' if anything in view came from a replayed capture. */
  captureMode: CaptureMode | null;
  labRunId: string | null;
  /** When data last arrived, for the offline pill and stale banners. */
  lastDataAt: Date | null;
  setPaused: (paused: boolean) => void;
  retryNow: () => void;
  reload: () => void;
  /**
   * Listen to every /ws/events message, not just events. Screens that own
   * findings, incidents, links or actions subscribe here rather than opening a
   * second socket. Returns an unsubscribe function.
   */
  subscribe: (handler: (message: WsMessage) => void) => () => void;
}

const LiveStoreContext = createContext<LiveStoreValue | null>(null);

export function LiveStoreProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<SocEvent[]>([]);
  const [receivedCount, setReceivedCount] = useState(0);
  const [snapshotMaxSeq, setSnapshotMaxSeq] = useState(0);
  const [status, setStatus] = useState<ConnectionStatus>({ state: 'connecting', attempt: 0 });
  const [paused, setPausedState] = useState(false);
  const [bufferedCount, setBufferedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [lastDataAt, setLastDataAt] = useState<Date | null>(null);

  /** Highest seq applied. The gate for every incoming message. */
  const lastSeqRef = useRef(0);
  const pausedRef = useRef(false);
  const bufferRef = useRef<SocEvent[]>([]);
  const streamRef = useRef<EventStream | null>(null);
  /** Guards against a late snapshot response overwriting a newer one. */
  const loadTokenRef = useRef(0);
  /** Screens listening for finding/incident/link/action messages. */
  const subscribersRef = useRef(new Set<(message: WsMessage) => void>());

  const subscribe = useCallback((handler: (message: WsMessage) => void) => {
    subscribersRef.current.add(handler);
    return () => {
      subscribersRef.current.delete(handler);
    };
  }, []);

  const appendEvents = useCallback((incoming: SocEvent[]) => {
    if (incoming.length === 0) return;
    setEvents((current) => {
      const merged = [...incoming, ...current];
      merged.sort((a, b) => b.seq - a.seq);
      return merged.slice(0, FEED_MAX_ROWS);
    });
    setReceivedCount((count) => count + incoming.length);
    setLastDataAt(new Date());
  }, []);

  const loadSnapshot = useCallback(async () => {
    const token = ++loadTokenRef.current;
    setLoading(true);
    try {
      const page = await fetchEvents({ limit: EVENTS_PAGE_LIMIT });
      if (token !== loadTokenRef.current) return;

      const ordered = [...page.items].sort((a, b) => b.seq - a.seq);
      const maxSeq = ordered.reduce((max, event) => Math.max(max, event.seq), 0);

      // Reconnect discards the list rather than patching the gap (API.md).
      lastSeqRef.current = maxSeq;
      bufferRef.current = [];
      setBufferedCount(0);
      setEvents(ordered.slice(0, FEED_MAX_ROWS));
      setReceivedCount(ordered.length);
      setSnapshotMaxSeq(maxSeq);
      setError(null);
      setLastDataAt(new Date());
    } catch (cause) {
      if (token !== loadTokenRef.current) return;
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError('unknown_error', 'Failed to load events.', 0),
      );
    } finally {
      if (token === loadTokenRef.current) setLoading(false);
    }
  }, []);

  const setPaused = useCallback(
    (next: boolean) => {
      pausedRef.current = next;
      setPausedState(next);
      if (!next && bufferRef.current.length > 0) {
        const flushed = bufferRef.current;
        bufferRef.current = [];
        setBufferedCount(0);
        appendEvents(flushed);
      }
    },
    [appendEvents],
  );

  // Load the snapshot on mount, independent of the socket. Without this, a
  // backend that is down leaves the feed on its skeleton forever, because
  // onConnected never fires and the REST failure is never surfaced.
  useEffect(() => {
    void loadSnapshot();
  }, [loadSnapshot]);

  useEffect(() => {
    const stream = createEventStream({
      onStatus: setStatus,
      onConnected: () => {
        void loadSnapshot();
      },
      onMessage: (message) => {
        // Hand every message to the screens listening for their own type.
        for (const handler of subscribersRef.current) handler(message);

        // Only events feed the live feed itself.
        if (message.type !== 'event') return;
        if (message.seq <= lastSeqRef.current) return;
        lastSeqRef.current = message.seq;

        const event = message.data as SocEvent;
        if (pausedRef.current) {
          bufferRef.current = [event, ...bufferRef.current].slice(0, FEED_MAX_ROWS);
          setBufferedCount(bufferRef.current.length);
          return;
        }
        appendEvents([event]);
      },
    });
    streamRef.current = stream;
    return () => {
      stream.close();
      streamRef.current = null;
    };
  }, [appendEvents, loadSnapshot]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await fetchHealth();
        if (!cancelled) setHealth(next);
      } catch {
        if (!cancelled) setHealth(null);
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 15_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const captureMode = useMemo<CaptureMode | null>(() => {
    if (events.length === 0) return null;
    return events.some((event) => event.capture_mode === 'replay') ? 'replay' : 'live';
  }, [events]);

  const labRunId = events[0]?.lab_run_id ?? null;

  const value = useMemo<LiveStoreValue>(
    () => ({
      events,
      receivedCount,
      snapshotMaxSeq,
      status,
      paused,
      bufferedCount,
      loading,
      error,
      health,
      captureMode,
      labRunId,
      lastDataAt,
      setPaused,
      retryNow: () => streamRef.current?.retryNow(),
      reload: () => void loadSnapshot(),
      subscribe,
    }),
    [
      events,
      receivedCount,
      snapshotMaxSeq,
      status,
      paused,
      bufferedCount,
      loading,
      error,
      health,
      captureMode,
      labRunId,
      lastDataAt,
      setPaused,
      loadSnapshot,
      subscribe,
    ],
  );

  return <LiveStoreContext.Provider value={value}>{children}</LiveStoreContext.Provider>;
}

export function useLiveStore(): LiveStoreValue {
  const value = useContext(LiveStoreContext);
  if (!value) throw new Error('useLiveStore must be used inside LiveStoreProvider');
  return value;
}
