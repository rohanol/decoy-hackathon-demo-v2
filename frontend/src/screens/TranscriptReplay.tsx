/**
 * Screen 5 — Transcript Replay. DESIGN_SPEC.md section 10.
 *
 * Replays what was typed at the emulated shell, line by line, with timestamps
 * and a clickable event id per line.
 *
 * The banner is mandatory and non-dismissible. It is the single most important
 * honesty statement in the whole UI (AGENTS.md section 7), and it sits above the
 * content, not below it. The terminal styling makes this look like a real
 * session, so the correction has to arrive before the impression does.
 *
 * Attacker text is rendered as-is: never interpreted, never syntax-highlighted,
 * always escaped and bounded.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { ApiError, fetchEvents, fetchTranscript } from '../api/client';
import { RawEventDrawer } from '../components/RawEventDrawer';
import { AttackerText, EmptyState, ErrorCard, SkeletonRows } from '../components/primitives';
import { COPY } from '../copy';
import { timeUtcZ } from '../lib/format';
import type { SocEvent, Transcript, TranscriptLineKind } from '../types/api';

/** Glyph and tone per line kind, consistent with the live feed (section 7.2). */
const LINE_STYLE: Record<TranscriptLineKind, { glyph: string; tone: string; label: string }> = {
  login_failed: { glyph: '✕', tone: 'warn', label: 'login failed' },
  login_ok: { glyph: '✓', tone: 'danger', label: 'login accepted' },
  command: { glyph: '▸', tone: 'accent', label: 'command' },
  close: { glyph: '●', tone: 'muted', label: 'connection closed' },
};

/** Playback pacing: real gaps, clamped so the demo never stalls or sprints. */
const MIN_STEP_MS = 400;
const MAX_STEP_MS = 2000;
const SPEEDS = [0.5, 1, 2] as const;

export function TranscriptReplay() {
  const { incidentId, sessionId } = useParams<{ incidentId: string; sessionId: string }>();

  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [eventsById, setEventsById] = useState<Map<string, SocEvent>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<number>(1);
  const [openEvent, setOpenEvent] = useState<SocEvent | null>(null);

  const load = useCallback(async () => {
    if (!incidentId || !sessionId) return;
    setLoading(true);
    try {
      const [loadedTranscript, eventsPage] = await Promise.all([
        fetchTranscript(incidentId, sessionId),
        fetchEvents({ incident_id: incidentId, limit: 200 }),
      ]);
      setTranscript(loadedTranscript);
      setEventsById(new Map(eventsPage.items.map((event) => [event.event_id, event])));
      // Default: fully revealed, paused at the end. Someone arriving from an
      // evidence link wants to see everything; stepping is opt-in.
      setStep(Math.max(0, loadedTranscript.lines.length - 1));
      setError(null);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError('transcript_load_failed', 'Could not load this transcript.', 0),
      );
    } finally {
      setLoading(false);
    }
  }, [incidentId, sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const lines = useMemo(() => transcript?.lines ?? [], [transcript]);
  const lastIndex = Math.max(0, lines.length - 1);
  const atEnd = step >= lastIndex;

  // Auto-advance using the real gap to the next line.
  const playTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!playing || lines.length === 0) return;
    if (atEnd) {
      setPlaying(false);
      return;
    }
    const current = lines[step];
    const next = lines[step + 1];
    if (!current || !next) return;

    const realGap = new Date(next.occurred_at).getTime() - new Date(current.occurred_at).getTime();
    const delay = Math.min(MAX_STEP_MS, Math.max(MIN_STEP_MS, realGap)) / speed;

    playTimer.current = setTimeout(() => setStep((value) => value + 1), delay);
    return () => {
      if (playTimer.current) clearTimeout(playTimer.current);
    };
  }, [playing, step, lines, atEnd, speed]);

  const goFirst = useCallback(() => {
    setPlaying(false);
    setStep(0);
  }, []);
  const goLast = useCallback(() => {
    setPlaying(false);
    setStep(lastIndex);
  }, [lastIndex]);
  const stepBack = useCallback(() => {
    setPlaying(false);
    setStep((value) => Math.max(0, value - 1));
  }, []);
  const stepForward = useCallback(() => {
    setPlaying(false);
    setStep((value) => Math.min(lastIndex, value + 1));
  }, [lastIndex]);
  const togglePlay = useCallback(() => {
    if (atEnd) {
      setStep(0);
      setPlaying(true);
      return;
    }
    setPlaying((value) => !value);
  }, [atEnd]);

  // Judges hand the laptop back and forth; keyboard control reads as competence.
  useEffect(() => {
    const onKeyDown = (keyEvent: KeyboardEvent) => {
      if (openEvent) return;
      switch (keyEvent.key) {
        case 'ArrowLeft':
          keyEvent.preventDefault();
          stepBack();
          break;
        case 'ArrowRight':
          keyEvent.preventDefault();
          stepForward();
          break;
        case ' ':
          keyEvent.preventDefault();
          togglePlay();
          break;
        case 'Home':
          keyEvent.preventDefault();
          goFirst();
          break;
        case 'End':
          keyEvent.preventDefault();
          goLast();
          break;
        default:
          break;
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [stepBack, stepForward, togglePlay, goFirst, goLast, openEvent]);

  /** The username from the accepted login, for the prompt prefix. */
  const promptUser = useMemo(
    () => lines.find((line) => line.kind === 'login_ok')?.text ?? '',
    [lines],
  );

  if (loading && transcript === null) {
    return (
      <div className="page">
        <section className="card">
          <SkeletonRows rows={8} />
        </section>
      </div>
    );
  }

  if (error && transcript === null) {
    return (
      <div className="page">
        <div className="page__head">
          <RouterLink to={`/incidents/${incidentId}`} className="btn btn--ghost">
            ← Incident
          </RouterLink>
        </div>
        <ErrorCard error={error} onRetry={() => void load()} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page__head">
        <RouterLink to={`/incidents/${incidentId}`} className="btn btn--ghost">
          ← {incidentId}
        </RouterLink>
        <span className="page__head-spacer" />
        <span className="toolbar__count">
          session {transcript?.session_id} · {lines.length} line
          {lines.length === 1 ? '' : 's'}
        </span>
      </div>

      <section className="card">
        {/* Mandatory, non-dismissible, above the content. */}
        <div className="banner banner--warn" role="note">
          <span aria-hidden="true">⚠</span>
          {COPY.transcriptBanner}
        </div>

        {lines.length === 0 ? (
          <EmptyState title={COPY.emptyTranscriptTitle} hint={COPY.emptyTranscriptHint} />
        ) : (
          <>
            <div className="terminal">
              {lines.slice(0, step + 1).map((line, index) => {
                const style = LINE_STYLE[line.kind];
                const event = eventsById.get(line.event_id);
                return (
                  <div
                    key={line.event_id}
                    className={index === step ? 'tline tline--current' : 'tline'}
                  >
                    <span className="tline__time">{timeUtcZ(line.occurred_at)}</span>
                    <span className={`tline__glyph tline__glyph--${style.tone}`}>
                      {style.glyph}
                    </span>
                    <span className="tline__text">
                      {line.kind === 'command' ? (
                        <>
                          <span className="tline__prompt">
                            {promptUser ? `${promptUser}@ssh-decoy-01:~$ ` : '$ '}
                          </span>
                          <AttackerText value={line.text} />
                        </>
                      ) : (
                        <>
                          <span className="tline__kind">{style.label}</span>
                          {line.text && line.kind !== 'close' ? (
                            <AttackerText value={line.text} />
                          ) : null}
                        </>
                      )}
                    </span>
                    {event ? (
                      <button
                        type="button"
                        className="tline__evid"
                        onClick={() => setOpenEvent(event)}
                        title="Open the raw event"
                      >
                        {line.event_id}
                      </button>
                    ) : (
                      <span className="tline__evid tline__evid--plain">{line.event_id}</span>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="replaybar">
              <button type="button" className="btn" onClick={goFirst} title="First line (Home)">
                ⏮
              </button>
              <button
                type="button"
                className="btn"
                onClick={stepBack}
                disabled={step === 0}
                title="Previous line (←)"
              >
                ◀
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={togglePlay}
                title="Play or pause (Space)"
              >
                {playing ? '❚❚ Pause' : atEnd ? '▶ Replay' : '▶ Play'}
              </button>
              <button
                type="button"
                className="btn"
                onClick={stepForward}
                disabled={atEnd}
                title="Next line (→)"
              >
                ▶▶
              </button>
              <button type="button" className="btn" onClick={goLast} title="Last line (End)">
                ⏭
              </button>

              <span className="replaybar__step mono">
                step {step + 1} / {lines.length}
              </span>

              <span className="toolbar__spacer" />

              <label className="replaybar__speed">
                <span className="label">speed</span>
                <select
                  className="select"
                  value={speed}
                  onChange={(changeEvent) => setSpeed(Number(changeEvent.target.value))}
                >
                  {SPEEDS.map((value) => (
                    <option key={value} value={value}>
                      {value}×
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </>
        )}
      </section>

      {openEvent ? (
        <RawEventDrawer event={openEvent} onClose={() => setOpenEvent(null)} />
      ) : null}
    </div>
  );
}
