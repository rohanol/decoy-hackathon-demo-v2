/**
 * The wording dictionary. AGENTS.md section 7 is a hard constraint, not a style
 * preference: labels must match evidence.
 *
 * Every user-facing string about what the system observed lives here, so the
 * language cannot drift as screens get built. If a phrase is not in this file,
 * check AGENTS.md section 7 before inventing one.
 *
 * Never: "compromised", "exploited", "breached", "attacker isolated",
 * "identified", "data stolen", "attack stopped", "safe", "clear".
 */

import type { EventType, LinkKind, LinkStatus, ActionStatus, Stage } from './types/api';

export const EVENT_TYPE_LABEL: Record<EventType, string> = {
  connection_open: 'connection open',
  auth_failure: 'auth failure',
  auth_success: 'auth accepted',
  command_input: 'command submitted',
  connection_close: 'connection close',
  http_request: 'http request',
  synthetic_file_access: 'synthetic file access',
  blocked_request: 'blocked request',
};

/** Longer form, used in the raw event drawer and tooltips. */
export const EVENT_TYPE_DESCRIPTION: Record<EventType, string> = {
  connection_open: 'A connection was opened to the decoy.',
  auth_failure: 'A login attempt was rejected by the decoy.',
  auth_success: 'Credentials were accepted by the emulated shell. No real account exists.',
  command_input: 'A command was submitted to the emulated shell. Nothing executed on a real host.',
  connection_close: 'The connection was closed.',
  http_request: 'An HTTP request reached the web decoy.',
  synthetic_file_access: 'A synthetic file was served. No real data exists in this lab.',
  blocked_request: 'A request was rejected by an analyst-applied block.',
};

export const SENSOR_LABEL: Record<string, string> = {
  'ssh-decoy-01': 'SSH decoy',
  'web-decoy-01': 'Web decoy',
};

export const STAGE_LABEL: Record<Stage, string> = {
  recon: 'recon',
  credential_attack: 'credential attack',
  exploit_attempt: 'exploit attempt',
  post_access: 'post-access',
  data_access: 'data access',
  none: 'no stage',
};

/** Shown in a kill-chain segment the incident never reached. Never "safe". */
export const STAGE_NOT_OBSERVED = 'not observed';

export function linkPhrase(kind: LinkKind, status: LinkStatus): string {
  if (status === 'confirmed') return 'analyst-confirmed link';
  if (status === 'rejected') return 'link rejected by analyst';
  return kind === 'strong_candidate'
    ? 'strong candidate link — honeytoken reuse'
    : 'candidate link';
}

export const ACTION_STATUS_LABEL: Record<ActionStatus, string> = {
  applied: 'APPLIED',
  verified: 'VERIFIED',
  expired: 'EXPIRED',
  revoked: 'REVOKED',
};

export const ACTION_STATUS_MEANING: Record<ActionStatus, string> = {
  applied: 'Block written. Not yet proven to reject a request.',
  verified: 'A blocked request arrived carrying this action id.',
  expired: 'The time limit ran out and the block lifted itself.',
  revoked: 'An analyst undid this block.',
};

export const COPY = {
  /** Non-dismissible banner above every transcript replay. */
  transcriptBanner:
    'Commands submitted to an emulated shell. Nothing executed on a real host.',

  /** Closing caveat in the link decision modal. From scenarios/demo_p3.md. */
  linkCaveat:
    'A confirmed link means the same source followed our planted trail. It does not identify a person.',

  /** Scope warning in the block preview. */
  blockScopeWarning:
    'This blocks the web decoy only. The SSH decoy stays reachable. This does not isolate the host.',

  blockScopeAck: 'I understand this blocks the web decoy only',

  blockAwaitingVerification: 'Applied. Waiting for a blocked request to verify.',

  noiseCounterNote: 'Deduplicated sensor records grouped by source IP and lab run.',

  lowPriorityTooltip: 'Scored below the noise threshold set in scoring.yaml.',

  exportTooltip: 'JSON export, password hashes excluded.',

  emptyFeedTitle: 'No events yet.',
  emptyFeedHint: 'Events appear here as soon as a decoy is touched.',

  emptyIncidentsTitle: 'No incidents yet.',
  emptyIncidentsHint: 'An incident opens the first time a source IP touches a decoy.',

  emptyTranscriptTitle: 'No commands recorded for this session.',
  emptyTranscriptHint: 'Brute-force sessions never reached a shell, so there is nothing to replay.',

  fixturesWarning:
    'Fixture data from contracts/examples/events_p3.json. Not a live capture.',
} as const;
