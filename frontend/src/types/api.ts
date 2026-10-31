/**
 * Hand-written from contracts/event.schema.json, contracts/finding.schema.json
 * and contracts/API.md (v1.0).
 *
 * Replace with generated types once M3's backend serves /openapi.json:
 *   npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/types/api.ts
 *
 * These are a frozen interface (AGENTS.md section 3). If the backend disagrees
 * with this file, the contract changes by PR with Rohan's OK — we do not patch
 * around it in the UI.
 */

export type SensorId = 'ssh-decoy-01' | 'web-decoy-01';

export const SENSOR_IDS: readonly SensorId[] = ['ssh-decoy-01', 'web-decoy-01'];

export type EventType =
  | 'connection_open'
  | 'auth_failure'
  | 'auth_success'
  | 'command_input'
  | 'connection_close'
  | 'http_request'
  | 'synthetic_file_access'
  | 'blocked_request';

export const EVENT_TYPES: readonly EventType[] = [
  'connection_open',
  'auth_failure',
  'auth_success',
  'command_input',
  'connection_close',
  'http_request',
  'synthetic_file_access',
  'blocked_request',
];

export type CaptureMode = 'live' | 'replay';
export type ResponseClass = 'normal' | 'fake_error' | 'fake_data' | 'blocked';
export type AccessOutcome = 'served' | 'denied' | 'not_found';

export interface EventAttributes {
  username?: string;
  /** sha256 only. Never rendered in a feed row. */
  password_sha256?: string;
  client_version?: string;
  command?: string;
  method?: string;
  path?: string;
  /** Honeytoken and password values already replaced with <redacted> by the adapter. */
  query_redacted?: string;
  user_agent?: string;
  status_code?: number;
  response_class?: ResponseClass;
  honeytoken_id?: string;
  asset_id?: string;
  size_bytes?: number;
  sha256?: string;
  outcome?: AccessOutcome;
  block_action_id?: string;
  [key: string]: unknown;
}

/** Exactly what the adapter POSTs to /api/ingest/events. */
export interface IngestEvent {
  schema_version: '1.0';
  source_record_id: string;
  sensor_id: SensorId;
  event_type: EventType;
  occurred_at: string;
  src_ip: string;
  src_port?: number | null;
  session_id?: string | null;
  lab_run_id: string;
  capture_mode: CaptureMode;
  attributes?: EventAttributes;
}

/** What GET /api/events returns: ingest fields plus backend-issued identity. */
export interface SocEvent extends IngestEvent {
  event_id: string;
  seq: number;
  ingested_at: string;
  incident_id?: string | null;
}

export interface EventsPage {
  items: SocEvent[];
  next_seq: number;
}

export type RuleId = 'R01' | 'R02' | 'R03' | 'R04' | 'R05' | 'R07' | 'R08' | 'R09';

/** Fixed display order. There is deliberately no R06. */
export const RULE_IDS: readonly RuleId[] = ['R01', 'R02', 'R03', 'R04', 'R05', 'R07', 'R08', 'R09'];

export type Stage =
  | 'recon'
  | 'credential_attack'
  | 'exploit_attempt'
  | 'post_access'
  | 'data_access'
  | 'none';

/** The five kill-chain segments, in fixed order. 'none' is not a segment. */
export const KILL_CHAIN_STAGES: readonly Exclude<Stage, 'none'>[] = [
  'recon',
  'credential_attack',
  'exploit_attempt',
  'post_access',
  'data_access',
];

export type Severity = 'low' | 'medium' | 'high' | 'critical';

export type WebAttackClass = 'sqli' | 'xss' | 'lfi' | 'rfi' | 'cmd_injection';

export interface Finding {
  finding_id: string;
  rule_id: RuleId;
  rule_version: string;
  incident_id: string;
  src_ip: string;
  technique_ids: string[];
  stage: Stage;
  label: string;
  limitation: string;
  evidence_event_ids: string[];
  points?: number;
  pending_confirmation?: boolean;
  web_attack_class?: WebAttackClass[];
  created_at: string;
}

export interface IncidentSummary {
  incident_id: string;
  src_ip: string;
  lab_run_id: string;
  score: number;
  severity: Severity;
  stages_observed: Stage[];
  first_seen: string;
  last_seen: string;
  event_count: number;
}

export interface ScoreBreakdownRow {
  rule_id: RuleId;
  points: number;
  counted: boolean;
  reason: string;
}

export interface IncidentSession {
  session_id: string;
  sensor_id: SensorId;
  started_at: string;
  commands: number;
}

export interface IncidentSummaryText {
  source: 'rules' | 'llm';
  text: string;
  cited_event_ids: string[];
}

export interface Incident extends IncidentSummary {
  findings: Finding[];
  score_breakdown: ScoreBreakdownRow[];
  links: Link[];
  sessions: IncidentSession[];
  summary: IncidentSummaryText;
  active_block: ResponseAction | null;
}

export type LinkKind = 'candidate' | 'strong_candidate';
export type LinkStatus = 'open' | 'confirmed' | 'rejected';

export interface Link {
  link_id: string;
  from_event_id: string;
  to_event_id: string;
  from_sensor: SensorId;
  to_sensor: SensorId;
  kind: LinkKind;
  basis: string;
  status: LinkStatus;
  decided_at: string | null;
  rationale: string | null;
}

export type TranscriptLineKind = 'login_failed' | 'login_ok' | 'command' | 'close';

export interface TranscriptLine {
  event_id: string;
  occurred_at: string;
  kind: TranscriptLineKind;
  text: string;
}

export interface Transcript {
  session_id: string;
  lines: TranscriptLine[];
}

export interface StatsOverview {
  raw_events: number;
  incidents: number;
  low_priority_incidents: number;
  findings_by_rule: Partial<Record<RuleId, number>>;
  first_alert_seconds: number | null;
}

export interface Health {
  ok: boolean;
  /** Last event time per sensor, or null if that sensor has produced nothing. */
  sensors: Record<string, string | null>;
}

export type ActionStatus = 'applied' | 'verified' | 'expired' | 'revoked';

export interface ResponseAction {
  action_id: string;
  target_ip: string;
  status: ActionStatus;
  reason: string;
  created_at: string;
  until: string;
  verified_by_event_id: string | null;
}

export interface BlockPreview {
  preview_id: string;
  target_ip: string;
  scope: string;
  ttl_seconds: number;
  expires_at: string;
}

/** Error envelope: {"error": {"code": "...", "message": "..."}} */
export interface ApiErrorBody {
  error: { code: string; message: string };
}

export type WsMessageType = 'event' | 'finding' | 'incident' | 'link' | 'action';

export interface WsMessage {
  seq: number;
  type: WsMessageType;
  data: unknown;
}
