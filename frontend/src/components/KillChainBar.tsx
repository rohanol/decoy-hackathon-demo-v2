/**
 * Kill-chain bar. DESIGN_SPEC.md section 9.2.
 *
 * Always all five segments, always the same order — the shape of the bar is the
 * at-a-glance read, so it must not reflow between incidents.
 *
 * An unobserved stage says "not observed", never "safe" or "clear"
 * (AGENTS.md section 7). Absence of evidence is not evidence of absence, and
 * the decoys only see what touched them.
 */

import { STAGE_LABEL, STAGE_NOT_OBSERVED } from '../copy';
import { KILL_CHAIN_STAGES, type Finding, type Severity, type Stage } from '../types/api';

/**
 * Compact variant for the incident list: the same five segments and the same
 * order, without the rule codes. The silhouette has to be comparable across
 * cards at a glance, so it uses the identical grid.
 */
export function KillChainStrip({
  stagesObserved,
  severity,
}: {
  stagesObserved: Stage[];
  severity: Severity;
}) {
  const observed = new Set(stagesObserved);
  return (
    <div className="killchain killchain--compact">
      {KILL_CHAIN_STAGES.map((stage) => {
        const isObserved = observed.has(stage);
        const classes = [
          'killchain__seg',
          isObserved
            ? `killchain__seg--observed killchain__seg--${severity}`
            : 'killchain__seg--unobserved',
        ].join(' ');
        return (
          <div
            key={stage}
            className={classes}
            title={`${STAGE_LABEL[stage]}: ${isObserved ? 'observed' : STAGE_NOT_OBSERVED}`}
          >
            <span className="killchain__fill" aria-hidden="true" />
            <span className="killchain__name">{STAGE_LABEL[stage]}</span>
          </div>
        );
      })}
    </div>
  );
}

export function KillChainBar({
  stagesObserved,
  findings,
  severity,
  activeStage,
  onStageClick,
}: {
  stagesObserved: Stage[];
  findings: Finding[];
  severity: Severity;
  activeStage?: Stage | null;
  onStageClick?: (stage: Stage) => void;
}) {
  const observed = new Set(stagesObserved);

  return (
    <div className="killchain">
      {KILL_CHAIN_STAGES.map((stage) => {
        const isObserved = observed.has(stage);
        // Rule codes evidencing this stage, from the findings themselves.
        const rules = findings
          .filter((finding) => finding.stage === stage)
          .map((finding) => finding.rule_id);
        const uniqueRules = [...new Set(rules)];
        const isActive = activeStage === stage;

        const classes = [
          'killchain__seg',
          isObserved ? 'killchain__seg--observed' : 'killchain__seg--unobserved',
          isObserved ? `killchain__seg--${severity}` : '',
          isActive ? 'is-active' : '',
        ]
          .filter(Boolean)
          .join(' ');

        const content = (
          <>
            <span className="killchain__fill" aria-hidden="true" />
            <span className="killchain__name">{STAGE_LABEL[stage]}</span>
            <span className="killchain__rules">
              {isObserved ? uniqueRules.join(' ') || '—' : STAGE_NOT_OBSERVED}
            </span>
          </>
        );

        if (!isObserved || !onStageClick) {
          return (
            <div
              key={stage}
              className={classes}
              aria-label={`${STAGE_LABEL[stage]}: ${isObserved ? uniqueRules.join(' ') : STAGE_NOT_OBSERVED}`}
            >
              {content}
            </div>
          );
        }

        return (
          <button
            key={stage}
            type="button"
            className={classes}
            onClick={() => onStageClick(stage)}
            aria-pressed={isActive}
            title={isActive ? 'Clear the stage filter' : `Filter findings to ${STAGE_LABEL[stage]}`}
          >
            {content}
          </button>
        );
      })}
    </div>
  );
}
