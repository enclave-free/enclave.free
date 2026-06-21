import { Fragment } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Check } from 'lucide-react';

export interface WizardStepMeta {
  id: string;
  label: string;
  icon: LucideIcon;
}

interface OnboardingWizardStepperProps {
  steps: WizardStepMeta[];
  current: number;
  /** Returns true if the step at `index` can be navigated to. */
  isEnabled: (index: number) => boolean;
  onSelect: (index: number) => void;
}

/**
 * Horizontal progress path rendered above the wizard body. Every chip is the
 * SAME size (flex-1) — the active step is distinguished only by emphasis
 * (accent fill + glow + bolder text), never by being larger than its peers.
 * Disabled steps (e.g. not-yet-built phases) are dimmed and unclickable.
 */
export function OnboardingWizardStepper({
  steps,
  current,
  isEnabled,
  onSelect,
}: OnboardingWizardStepperProps) {
  return (
    <ol className="flex w-full items-stretch gap-2">
      {steps.map((step, index) => {
        const Icon = step.icon;
        const isActive = index === current;
        const isComplete = index < current;
        const enabled = isEnabled(index);
        const stepNumber = index + 1;

        return (
          <Fragment key={step.id}>
            {index > 0 && (
              <li aria-hidden className="flex flex-none items-center">
                <span className="block w-4 border-t border-dashed border-border sm:w-8" />
              </li>
            )}
            <li className="flex-1">
              <button
                type="button"
                disabled={!enabled}
                aria-current={isActive ? 'step' : undefined}
                onClick={() => enabled && onSelect(index)}
                className={[
                  'flex h-full w-full items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-all sm:gap-3 sm:px-4',
                  isActive
                    ? 'border-accent bg-accent/10 shadow-[0_0_0_1px_var(--color-accent),0_0_24px_-6px_var(--color-accent)]'
                    : 'border-border bg-surface-raised',
                  enabled && !isActive
                    ? 'cursor-pointer hover:border-accent/40 hover:bg-surface-overlay'
                    : '',
                  !enabled ? 'cursor-not-allowed opacity-50' : '',
                ].join(' ')}
              >
                <span
                  className={[
                    'flex h-7 w-7 flex-none items-center justify-center rounded-full text-xs font-semibold',
                    isActive
                      ? 'bg-accent text-accent-text'
                      : isComplete
                        ? 'bg-accent/20 text-accent'
                        : 'bg-surface-overlay text-text-muted',
                  ].join(' ')}
                >
                  {isComplete ? <Check className="h-4 w-4" /> : stepNumber}
                </span>
                <Icon
                  className={[
                    'h-4 w-4 flex-none',
                    isActive ? 'text-accent' : 'text-text-muted',
                  ].join(' ')}
                />
                <span
                  className={[
                    'min-w-0 truncate text-sm',
                    isActive
                      ? 'font-semibold text-text'
                      : 'font-medium text-text-secondary',
                  ].join(' ')}
                >
                  {step.label}
                </span>
              </button>
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}
