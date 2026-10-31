/**
 * Formatting helpers. All timestamps are UTC — the lab runs in UTC and the
 * topbar carries a UTC clock so there is never a question about the zone
 * (AGENTS.md section 9: RFC 3339 UTC).
 */

/** "04:31:30" from an RFC 3339 timestamp. */
export function timeUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toISOString().slice(11, 19);
}

/** "04:31:30Z" — used where the zone needs to be explicit. */
export function timeUtcZ(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.toISOString().slice(11, 19)}Z`;
}

/** "2026-11-01 04:31:30Z" for the drawer. */
export function fullUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.toISOString().slice(0, 10)} ${date.toISOString().slice(11, 19)}Z`;
}

/** "4s ago", "2m ago", "1h ago". Relative to now. */
export function relativeFromNow(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '—';
  const seconds = Math.max(0, Math.round((now.getTime() - then.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** "3,728" */
export function number(value: number): string {
  return value.toLocaleString('en-US');
}

/** "3,728 B" */
export function bytes(value: number): string {
  return `${number(value)} B`;
}

/** Bound an attacker-controlled string for a table cell. */
export function clamp(value: string, max: number): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}

/** Hashes are shown truncated, and only in the drawer. */
export function shortHash(value: string): string {
  return value.length <= 12 ? value : `${value.slice(0, 12)}…`;
}
