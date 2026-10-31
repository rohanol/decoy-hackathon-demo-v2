/**
 * Runtime configuration. Read once at module load.
 *
 * AGENTS.md section 9: "Fixtures only in dev mode. Nothing fake on the demo
 * path." USE_FIXTURES defaults to false, and when it is on the topbar shows a
 * loud FIXTURES chip on every screen so fake data can never be mistaken for a
 * live capture.
 */

export const API_BASE: string = import.meta.env['VITE_API_BASE'] ?? 'http://127.0.0.1:8000';

export const USE_FIXTURES: boolean = import.meta.env['VITE_USE_FIXTURES'] === '1';

/** ws://127.0.0.1:8000/ws/events, derived from API_BASE. */
export function wsUrl(): string {
  const base = API_BASE.replace(/^http/, 'ws').replace(/\/$/, '');
  return `${base}/ws/events`;
}

/** Keep the rendered feed bounded; the DOM is not a database. */
export const FEED_MAX_ROWS = 500;

/** REST snapshot page size, matching the API.md default. */
export const EVENTS_PAGE_LIMIT = 200;
