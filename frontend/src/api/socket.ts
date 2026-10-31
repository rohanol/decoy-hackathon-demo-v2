/**
 * /ws/events client with exponential backoff.
 *
 * API.md: the client loads a REST snapshot on connect, then applies messages
 * with a seq greater than the last one seen. On reconnect it reloads the
 * snapshot rather than trying to patch the gap — the store owns that part, this
 * module just reports when a (re)connection happened.
 *
 * In fixture mode this transparently drives the fake socket instead.
 */

import { USE_FIXTURES, wsUrl } from './config';
import { openFixtureSocket, type FixtureSocket } from './fixtures';
import type { WsMessage } from '../types/api';

export type ConnectionState = 'connecting' | 'live' | 'reconnecting' | 'offline';

export interface ConnectionStatus {
  state: ConnectionState;
  /** Retry number while reconnecting, 0 otherwise. */
  attempt: number;
}

export interface EventStreamHandlers {
  onMessage: (message: WsMessage) => void;
  onStatus: (status: ConnectionStatus) => void;
  /** Fired on every successful (re)connection. The store reloads its snapshot. */
  onConnected: () => void;
}

export interface EventStream {
  close: () => void;
  /** Used by the connection pill when offline: skip the backoff and try now. */
  retryNow: () => void;
}

const BACKOFF_MS = [500, 1000, 2000, 4000, 8000] as const;
const MAX_ATTEMPTS = 6;

function backoffFor(attempt: number): number {
  const base = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)] ?? 8000;
  // Jitter ±20% so a reconnect storm does not synchronise.
  return Math.round(base * (0.8 + Math.random() * 0.4));
}

function isWsMessage(value: unknown): value is WsMessage {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as { seq?: unknown; type?: unknown };
  return typeof candidate.seq === 'number' && typeof candidate.type === 'string';
}

export function createEventStream(handlers: EventStreamHandlers): EventStream {
  if (USE_FIXTURES) {
    let socket: FixtureSocket | null = null;
    // Defer so the caller's snapshot load lands before the first streamed event.
    const start = setTimeout(() => {
      socket = openFixtureSocket(handlers.onMessage);
      handlers.onStatus({ state: 'live', attempt: 0 });
      handlers.onConnected();
    }, 300);

    return {
      close: () => {
        clearTimeout(start);
        socket?.close();
      },
      retryNow: () => {
        /* nothing to retry: the fixture socket never drops */
      },
    };
  }

  let ws: WebSocket | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let attempt = 0;
  let closedByUs = false;

  function clearRetry(): void {
    if (retryTimer !== null) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
  }

  function scheduleRetry(): void {
    if (closedByUs) return;

    if (attempt >= MAX_ATTEMPTS) {
      handlers.onStatus({ state: 'offline', attempt });
      return;
    }

    attempt += 1;
    handlers.onStatus({ state: 'reconnecting', attempt });
    clearRetry();
    retryTimer = setTimeout(connect, backoffFor(attempt - 1));
  }

  function connect(): void {
    if (closedByUs) return;
    clearRetry();

    let socket: WebSocket;
    try {
      socket = new WebSocket(wsUrl());
    } catch {
      scheduleRetry();
      return;
    }
    ws = socket;

    socket.onopen = () => {
      attempt = 0;
      handlers.onStatus({ state: 'live', attempt: 0 });
      handlers.onConnected();
    };

    socket.onmessage = (frame: MessageEvent<string>) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(frame.data);
      } catch {
        return; // a malformed frame is not worth tearing the connection down for
      }
      if (isWsMessage(parsed)) handlers.onMessage(parsed);
    };

    socket.onerror = () => {
      // onclose always follows; the retry is scheduled there.
    };

    socket.onclose = () => {
      ws = null;
      scheduleRetry();
    };
  }

  handlers.onStatus({ state: 'connecting', attempt: 0 });
  connect();

  return {
    close: () => {
      closedByUs = true;
      clearRetry();
      ws?.close();
      ws = null;
    },
    retryNow: () => {
      attempt = 0;
      clearRetry();
      connect();
    },
  };
}
