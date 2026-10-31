/**
 * Glyph and colour per event type. DESIGN_SPEC.md section 7.2.
 *
 * Two deliberate inversions, worth being able to explain to a judge:
 *  - auth_success is red, not green. A successful login to a decoy is the bad news.
 *  - blocked_request is green. It means an analyst's block is working.
 *
 * Colour never carries the meaning on its own: every row also shows the text
 * label from copy.ts.
 */

import type { EventType } from '../types/api';

export type GlyphTone = 'secondary' | 'muted' | 'accent' | 'warn' | 'danger' | 'ok';

interface EventStyle {
  glyph: string;
  tone: GlyphTone;
}

export const EVENT_STYLE: Record<EventType, EventStyle> = {
  connection_open: { glyph: '○', tone: 'secondary' },
  auth_failure: { glyph: '✕', tone: 'warn' },
  auth_success: { glyph: '✓', tone: 'danger' },
  command_input: { glyph: '▸', tone: 'accent' },
  connection_close: { glyph: '●', tone: 'muted' },
  http_request: { glyph: '◆', tone: 'accent' },
  synthetic_file_access: { glyph: '◆', tone: 'danger' },
  blocked_request: { glyph: '⊘', tone: 'ok' },
};
