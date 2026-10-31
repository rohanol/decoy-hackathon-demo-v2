/**
 * Score breakdown. DESIGN_SPEC.md section 9.3.
 *
 * Shows every rule the backend reported, counted and uncounted alike, with the
 * reason it gave. Uncounted rows are a credibility feature, not clutter: they
 * show the score is bounded by rules rather than inflated by repetition.
 *
 * Law 1: the displayed score is the API's `score`. The raw sum below is
 * presented only as a transparency aid, explicitly labelled "raw", and is never
 * substituted for the real score.
 */

import { number } from '../lib/format';
import type { ScoreBreakdownRow } from '../types/api';

export function ScoreBreakdown({ rows, score }: { rows: ScoreBreakdownRow[]; score: number }) {
  const rawSum = rows.reduce((total, row) => total + row.points, 0);
  const capped = rawSum > score;

  return (
    <>
      <table className="breakdown">
        <thead>
          <tr>
            <th scope="col">Rule</th>
            <th scope="col" className="breakdown__num">
              Pts
            </th>
            <th scope="col">Counted</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.rule_id} className={row.counted ? '' : 'breakdown__row--uncounted'}>
              <td className="mono">{row.rule_id}</td>
              <td className="breakdown__num mono">{row.counted ? row.points : '—'}</td>
              <td>
                {row.counted ? <span className="breakdown__tick">✓</span> : null}
                <span className="breakdown__reason">{row.reason}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="breakdown__total">
        {capped ? (
          <>
            raw {number(rawSum)} · capped at {number(score)} → <strong>{number(score)}</strong>
          </>
        ) : (
          <>
            total <strong>{number(score)}</strong>
          </>
        )}
      </div>
    </>
  );
}
