/** Shared primitives. DESIGN_SPEC.md sections 2 and 15. */

import type { ReactNode } from 'react';
import type { ApiError } from '../api/client';

export function Dot({
  tone,
  animate,
}: {
  tone: 'ok' | 'warn' | 'danger' | 'neutral';
  animate?: 'pulse' | 'blink';
}) {
  const classes = ['dot', `dot--${tone}`];
  if (animate) classes.push(`dot--${animate}`);
  return <span className={classes.join(' ')} aria-hidden="true" />;
}

/**
 * Law 2: attacker-controlled text. Rendered as plain React children (escaped),
 * in mono, bounded so it cannot break layout no matter what was sent.
 * There is deliberately no way to pass HTML through this component.
 */
export function AttackerText({ value, well }: { value: string; well?: boolean }) {
  return (
    <span className={well ? 'attacker-text attacker-text--well' : 'attacker-text'}>{value}</span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="state">
      <div className="state__title">{title}</div>
      <div className="state__hint">{hint}</div>
    </div>
  );
}

export function ErrorCard({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className="errorcard" role="alert">
      <span className="errorcard__code">{error.code}</span>
      <span>{error.message}</span>
      {onRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function SkeletonRows({ rows = 8 }: { rows?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)', padding: 'var(--s4)' }}>
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="skeleton"
          style={{ width: `${[94, 72, 86, 61, 90, 68, 80, 74][index % 8]}%` }}
        />
      ))}
    </div>
  );
}

export function Card({
  title,
  actions,
  children,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card">
      {title !== undefined ? (
        <header className="card__head">
          <span>{title}</span>
          {actions ? <span style={{ marginLeft: 'auto' }}>{actions}</span> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

/** Mono value with a copy button. Used for IDs and hashes in the drawer. */
export function CopyableValue({ value, display }: { value: string; display?: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 2 }}>
      <span className="mono">{display ?? value}</span>
      <button
        type="button"
        className="copybtn"
        title="Copy to clipboard"
        onClick={() => {
          void navigator.clipboard?.writeText(value);
        }}
      >
        copy
      </button>
    </span>
  );
}
