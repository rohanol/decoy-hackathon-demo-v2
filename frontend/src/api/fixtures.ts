/**
 * Fixture backend. Stands in for M3's API so the whole UI can be built before
 * the backend exists (M1_frontend.md step 0b).
 *
 * This module IS the mock backend, so it is the one place allowed to synthesise
 * backend-issued fields (event_id, seq, ingested_at, incident_id). Screens must
 * never do this — they display what the API gives them.
 *
 * The fixture is imported read-only from contracts/, which M3 owns. It is not
 * copied into frontend/, so it cannot drift from the contract.
 *
 * Behaviour: the first N-10 events come back from the REST snapshot, the last 10
 * arrive over the fake socket on a timer. That exercises both code paths — the
 * snapshot and the live append — which is the whole point of having fixtures.
 */

import fixtureFile from '../../../contracts/examples/events_p3.json';
import type {
  EventsPage,
  Finding,
  Health,
  Incident,
  IncidentSummary,
  IngestEvent,
  Link,
  ScoreBreakdownRow,
  SocEvent,
  Transcript,
  TranscriptLine,
  TranscriptLineKind,
  WsMessage,
} from '../types/api';
import type { EventsQuery } from './client';

/** How many trailing events are withheld from the snapshot and streamed live. */
const STREAMED_TAIL = 10;

/** Delay between streamed fixture events. */
const STREAM_INTERVAL_MS = 1200;

/** Simulated network latency, so loading states are actually visible in dev. */
const FAKE_LATENCY_MS = 180;

const rawEvents = (fixtureFile as { events: unknown[] }).events as unknown as IngestEvent[];

/**
 * Backend-issued fields, applied deterministically so a reload shows the same
 * IDs. incident_id groups by src_ip, which is what the real backend does
 * (AGENTS.md section 4: one incident per src_ip per lab_run_id).
 */
const ALL_EVENTS: SocEvent[] = (() => {
  const incidentBySrcIp = new Map<string, string>();
  return rawEvents.map((event, index) => {
    let incidentId = incidentBySrcIp.get(event.src_ip);
    if (!incidentId) {
      incidentId = `inc_${String(incidentBySrcIp.size + 1).padStart(2, '0')}`;
      incidentBySrcIp.set(event.src_ip, incidentId);
    }
    return {
      ...event,
      event_id: `evt_${event.source_record_id.slice(0, 8)}`,
      seq: index + 1,
      ingested_at: event.occurred_at,
      incident_id: incidentId,
    };
  });
})();

const SNAPSHOT_COUNT = Math.max(1, ALL_EVENTS.length - STREAMED_TAIL);

/**
 * Highest seq the fake backend has "committed". Grows as the stream advances, so
 * a reconnect-triggered snapshot reload returns everything released so far
 * rather than losing the streamed rows.
 */
let releasedSeq = ALL_EVENTS[SNAPSHOT_COUNT - 1]?.seq ?? 0;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function released(): SocEvent[] {
  return ALL_EVENTS.filter((event) => event.seq <= releasedSeq);
}

export async function fetchEvents(query: EventsQuery = {}): Promise<EventsPage> {
  await sleep(FAKE_LATENCY_MS);

  // The progressive-release gate exists to make the live feed stream. A query
  // for one incident is asking for that incident's record, which a real backend
  // would answer in full — so it bypasses the gate. Without this, evidence ids
  // on the incident page are unresolvable until the stream catches up.
  let items = query.incident_id ? ALL_EVENTS : released();
  if (query.incident_id) items = items.filter((e) => e.incident_id === query.incident_id);
  if (query.sensor_id) items = items.filter((e) => e.sensor_id === query.sensor_id);
  if (query.since_seq !== undefined) {
    const since = query.since_seq;
    items = items.filter((e) => e.seq > since);
  }

  const limit = query.limit ?? 200;
  // Newest first, matching how the feed renders.
  const ordered = [...items].sort((a, b) => b.seq - a.seq).slice(0, limit);
  const nextSeq = items.reduce((max, e) => Math.max(max, e.seq), 0);

  return { items: ordered, next_seq: nextSeq };
}

export async function fetchHealth(): Promise<Health> {
  await sleep(FAKE_LATENCY_MS);
  const sensors: Record<string, string | null> = {
    'ssh-decoy-01': null,
    'web-decoy-01': null,
  };
  for (const event of released()) {
    const current = sensors[event.sensor_id];
    if (current === null || current === undefined || event.occurred_at > current) {
      sensors[event.sensor_id] = event.occurred_at;
    }
  }
  return { ok: true, sensors };
}

/*
 * ---------------------------------------------------------------------------
 * Mock incident for inc_01.
 *
 * Hand-authored to match the P3 demo narrative in scenarios/demo_p3.md, citing
 * the real event ids this file generates. Scores and severities are NOT
 * computed here from the events — they are stand-in values written to match
 * config/scoring.yaml, exactly as the real backend would report them. Scoring
 * belongs to M3.
 *
 * Note which rules fire: R01, R02, R03, R04, R07, plus R05 and R09 once the
 * analyst confirms the link. R08 does NOT fire, because the fixture has no
 * hidden-path probing or 404 burst. That leaves the recon stage genuinely
 * unobserved, which is what the kill-chain bar should show.
 * ---------------------------------------------------------------------------
 */

const AUTH_FAILURE_EVENTS = [
  'evt_dba0082e',
  'evt_8c09b371',
  'evt_01dc6054',
  'evt_f3bc8220',
  'evt_4e90553f',
  'evt_b6b3be77',
];

/** Mutable: the analyst's decision changes it, as it would on the backend. */
let fixtureLink: Link = {
  link_id: 'lnk_01',
  from_event_id: 'evt_569c0a23',
  to_event_id: 'evt_9daf2fae',
  from_sensor: 'ssh-decoy-01',
  to_sensor: 'web-decoy-01',
  kind: 'strong_candidate',
  basis: 'honeytoken tok_portal_01',
  status: 'open',
  decided_at: null,
  rationale: null,
};

function buildFindings(linkConfirmed: boolean): Finding[] {
  return [
    {
      finding_id: 'fnd_01',
      rule_id: 'R01',
      rule_version: 'R01@1',
      incident_id: 'inc_01',
      src_ip: '192.168.77.10',
      technique_ids: ['T1110.001'],
      stage: 'credential_attack',
      label: 'Repeated SSH password guessing (6 failures in 60 s)',
      limitation: 'Does not show the account was compromised.',
      evidence_event_ids: AUTH_FAILURE_EVENTS,
      points: 25,
      created_at: '2026-11-01T04:30:11Z',
    },
    {
      finding_id: 'fnd_02',
      rule_id: 'R02',
      rule_version: 'R02@1',
      incident_id: 'inc_01',
      src_ip: '192.168.77.10',
      technique_ids: ['T1059.004'],
      stage: 'post_access',
      label: 'Commands submitted to the emulated shell after an accepted login',
      limitation: 'Nothing executed on a real host. The shell is emulated.',
      evidence_event_ids: ['evt_877b597a', 'evt_083bc808', 'evt_cb51c275', 'evt_569c0a23'],
      points: 15,
      created_at: '2026-11-01T04:30:23Z',
    },
    {
      finding_id: 'fnd_03',
      rule_id: 'R03',
      rule_version: 'R03@1',
      incident_id: 'inc_01',
      src_ip: '192.168.77.10',
      technique_ids: ['T1083'],
      stage: 'post_access',
      label: 'Directory listing attempted in the emulated shell',
      limitation: 'Shows a discovery attempt only. Nothing was enumerated on a real host.',
      evidence_event_ids: ['evt_cb51c275'],
      points: 10,
      created_at: '2026-11-01T04:30:27Z',
    },
    {
      finding_id: 'fnd_04',
      rule_id: 'R07',
      rule_version: 'R07@1',
      incident_id: 'inc_01',
      src_ip: '192.168.77.10',
      technique_ids: ['T1190'],
      stage: 'exploit_attempt',
      label: 'Web attack attempt against /search',
      limitation: 'Does not show successful exploitation. The decoy returned a canned error.',
      evidence_event_ids: ['evt_bc86cf44'],
      points: 15,
      web_attack_class: ['sqli'],
      created_at: '2026-11-01T04:31:20Z',
    },
    {
      finding_id: 'fnd_05',
      rule_id: 'R04',
      rule_version: 'R04@1',
      incident_id: 'inc_01',
      src_ip: '192.168.77.10',
      technique_ids: ['T1005'],
      stage: 'data_access',
      label: 'Synthetic file served (customer_data.csv)',
      limitation: 'The file was synthetic. No real data exists in this lab.',
      evidence_event_ids: ['evt_c2eeed76', 'evt_f06aa469'],
      points: 30,
      created_at: '2026-11-01T04:31:30Z',
    },
    {
      finding_id: 'fnd_06',
      rule_id: 'R09',
      rule_version: 'R09@1',
      incident_id: 'inc_01',
      src_ip: '192.168.77.10',
      technique_ids: [],
      stage: 'none',
      label: 'Honeytoken planted on ssh-decoy-01 presented on web-decoy-01',
      limitation: linkConfirmed
        ? 'Shows the same source followed our planted trail. Does not identify a person.'
        : 'Awaiting analyst confirmation.',
      evidence_event_ids: ['evt_569c0a23', 'evt_9daf2fae'],
      points: linkConfirmed ? 15 : 0,
      pending_confirmation: !linkConfirmed,
      created_at: '2026-11-01T04:31:10Z',
    },
    {
      finding_id: 'fnd_07',
      rule_id: 'R05',
      rule_version: 'R05@1',
      incident_id: 'inc_01',
      src_ip: '192.168.77.10',
      technique_ids: [],
      stage: 'none',
      label: 'Analyst-confirmed link between ssh-decoy-01 and web-decoy-01',
      limitation: linkConfirmed
        ? 'A confirmed link does not identify a person.'
        : 'Awaiting analyst confirmation.',
      evidence_event_ids: ['evt_569c0a23', 'evt_9daf2fae'],
      points: linkConfirmed ? 15 : 0,
      pending_confirmation: !linkConfirmed,
      created_at: '2026-11-01T04:31:10Z',
    },
  ];
}

function buildBreakdown(linkConfirmed: boolean): ScoreBreakdownRow[] {
  return [
    { rule_id: 'R01', points: 25, counted: true, reason: 'first R01' },
    { rule_id: 'R02', points: 15, counted: true, reason: 'first R02' },
    { rule_id: 'R03', points: 10, counted: true, reason: 'first R03' },
    { rule_id: 'R04', points: 30, counted: true, reason: 'first R04' },
    { rule_id: 'R07', points: 15, counted: true, reason: 'first R07' },
    {
      rule_id: 'R05',
      points: linkConfirmed ? 15 : 0,
      counted: linkConfirmed,
      reason: linkConfirmed ? 'link confirmed by analyst' : 'awaiting link confirmation',
    },
    {
      rule_id: 'R09',
      points: linkConfirmed ? 15 : 0,
      counted: linkConfirmed,
      reason: linkConfirmed ? 'link confirmed by analyst' : 'awaiting link confirmation',
    },
  ];
}

function summaryFor(linkConfirmed: boolean): string {
  const base =
    'Six SSH password attempts from 192.168.77.10 against dg_demo were rejected by the decoy, ' +
    'then one was accepted by the emulated shell. Three commands were submitted to the emulated ' +
    'shell. A web attack attempt reached /search on the web decoy, and a synthetic file was served.';
  return linkConfirmed
    ? `${base} An analyst confirmed that a honeytoken planted on ssh-decoy-01 was presented on web-decoy-01.`
    : `${base} A honeytoken planted on ssh-decoy-01 was presented on web-decoy-01, awaiting analyst confirmation.`;
}

function incidentSummary(): IncidentSummary {
  const confirmed = fixtureLink.status === 'confirmed';
  return {
    incident_id: 'inc_01',
    src_ip: '192.168.77.10',
    lab_run_id: 'run-fixture',
    // Stand-in values matching config/scoring.yaml. 95 before confirmation;
    // 125 raw after, capped at 100.
    score: confirmed ? 100 : 95,
    severity: 'critical',
    // No R08, so recon is genuinely not observed.
    stages_observed: ['credential_attack', 'exploit_attempt', 'post_access', 'data_access'],
    first_seen: '2026-11-01T04:30:00Z',
    last_seen: '2026-11-01T04:32:30Z',
    event_count: ALL_EVENTS.length,
  };
}

export async function fetchIncidents(): Promise<{ items: IncidentSummary[] }> {
  await sleep(FAKE_LATENCY_MS);
  return { items: [incidentSummary()] };
}

export async function fetchIncident(incidentId: string): Promise<Incident> {
  await sleep(FAKE_LATENCY_MS);
  if (incidentId !== 'inc_01') {
    throw new Error(`fixture has no incident ${incidentId}`);
  }
  const confirmed = fixtureLink.status === 'confirmed';
  return {
    ...incidentSummary(),
    findings: buildFindings(confirmed),
    score_breakdown: buildBreakdown(confirmed),
    links: [fixtureLink],
    sessions: [
      { session_id: 'hyd0', sensor_id: 'ssh-decoy-01', started_at: '2026-11-01T04:30:00Z', commands: 0 },
      { session_id: 'hyd1', sensor_id: 'ssh-decoy-01', started_at: '2026-11-01T04:30:02Z', commands: 0 },
      { session_id: 'hyd2', sensor_id: 'ssh-decoy-01', started_at: '2026-11-01T04:30:04Z', commands: 0 },
      { session_id: 'hyd3', sensor_id: 'ssh-decoy-01', started_at: '2026-11-01T04:30:06Z', commands: 0 },
      { session_id: 'hyd4', sensor_id: 'ssh-decoy-01', started_at: '2026-11-01T04:30:08Z', commands: 0 },
      { session_id: 'hyd5', sensor_id: 'ssh-decoy-01', started_at: '2026-11-01T04:30:10Z', commands: 0 },
      { session_id: 'sess01', sensor_id: 'ssh-decoy-01', started_at: '2026-11-01T04:30:20Z', commands: 3 },
    ],
    summary: {
      source: 'rules',
      text: summaryFor(confirmed),
      cited_event_ids: ['evt_dba0082e', 'evt_877b597a', 'evt_569c0a23', 'evt_bc86cf44', 'evt_f06aa469'],
    },
    active_block: null,
  };
}

/**
 * Transcript for one session, derived from the session's own events.
 *
 * Only the four kinds in the contract become lines. connection_open is not one
 * of them, so it is skipped: the transcript is what was attempted against the
 * shell, not the TCP story.
 */
export async function fetchTranscript(sessionId: string): Promise<Transcript> {
  await sleep(FAKE_LATENCY_MS);

  const lines: TranscriptLine[] = [];
  for (const event of ALL_EVENTS) {
    if (event.session_id !== sessionId) continue;
    const attributes = event.attributes ?? {};

    let kind: TranscriptLineKind | null = null;
    let text = '';
    switch (event.event_type) {
      case 'auth_failure':
        kind = 'login_failed';
        text = attributes.username ?? '';
        break;
      case 'auth_success':
        kind = 'login_ok';
        text = attributes.username ?? '';
        break;
      case 'command_input':
        kind = 'command';
        text = attributes.command ?? '';
        break;
      case 'connection_close':
        kind = 'close';
        text = 'connection closed';
        break;
      default:
        kind = null;
    }
    if (kind === null) continue;

    lines.push({ event_id: event.event_id, occurred_at: event.occurred_at, kind, text });
  }

  return { session_id: sessionId, lines };
}

export async function fetchLinks(): Promise<{ items: Link[] }> {
  await sleep(FAKE_LATENCY_MS);
  return { items: [fixtureLink] };
}

export async function postLinkDecision(
  linkId: string,
  decision: 'confirm' | 'reject',
  rationale: string,
): Promise<Link> {
  await sleep(FAKE_LATENCY_MS);
  if (linkId !== fixtureLink.link_id) throw new Error(`fixture has no link ${linkId}`);
  fixtureLink = {
    ...fixtureLink,
    status: decision === 'confirm' ? 'confirmed' : 'rejected',
    decided_at: new Date().toISOString(),
    rationale,
  };
  return fixtureLink;
}

export interface FixtureSocket {
  close: () => void;
}

/**
 * Fake WebSocket. Emits the withheld tail of the fixture as `type: "event"`
 * messages, in order, then goes quiet while staying "open".
 */
export function openFixtureSocket(onMessage: (message: WsMessage) => void): FixtureSocket {
  let index = SNAPSHOT_COUNT;
  let stopped = false;

  const timer = setInterval(() => {
    if (stopped) return;
    const event = ALL_EVENTS[index];
    if (!event) {
      clearInterval(timer);
      // A real backend pushes after each DB commit, so the incident summary
      // lands on the wire too. Emitting it here keeps the incident list's
      // live-update path exercised in fixture mode.
      onMessage({ seq: releasedSeq + 1, type: 'incident', data: incidentSummary() });
      return;
    }
    index += 1;
    releasedSeq = Math.max(releasedSeq, event.seq);
    onMessage({ seq: event.seq, type: 'event', data: event });
  }, STREAM_INTERVAL_MS);

  return {
    close: () => {
      stopped = true;
      clearInterval(timer);
    },
  };
}
