import { lazy, Suspense, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  Globe,
  MessageSquare,
  Settings2,
  Sparkles,
  User,
  Wand2,
  type LucideIcon,
} from 'lucide-react';
import { Button } from '../components/ui';
import { OnboardingWizardStepper } from '../components/admin/OnboardingWizardStepper';

const AdminConfigAssistant = lazy(() =>
  import('../components/admin/AdminConfigAssistant').then((module) => ({
    default: module.AdminConfigAssistant,
  }))
);
const AdminDocumentUpload = lazy(() =>
  import('./AdminDocumentUpload').then((module) => ({
    default: module.AdminDocumentUpload,
  }))
);
const AdminResourcesDirectory = lazy(() =>
  import('./AdminResourcesDirectory').then((module) => ({
    default: module.AdminResourcesDirectory,
  }))
);

interface WizardStep {
  id: 'initialize' | 'docs' | 'resources' | 'test' | 'feedback';
  label: string;
  icon: LucideIcon;
  title: string;
  subtitle: string;
  /** Not-yet-built phases: shown in the path, but not navigable. */
  stub?: boolean;
}

/**
 * AI-facilitated first-run onboarding, structured as a one-thing-at-a-time
 * wizard. A horizontal progress path renders above the active phase so the
 * operator always sees where they are; each phase presents a single clear task
 * with its own title, icon, and subtitle.
 *
 * Built phases: Initialize (guided chat), Upload Docs, Curated Resources.
 * Test-as-User and Feedback are stubbed in the path (owned by another track).
 */
export function AdminOnboardingSetup() {
  const { t } = useTranslation();
  const [current, setCurrent] = useState(0);

  const steps: WizardStep[] = [
    {
      id: 'initialize',
      label: t('adminGuidedSetup.steps.initialize.label', 'Initialize'),
      icon: Wand2,
      title: t('adminGuidedSetup.steps.initialize.title', 'Initialize'),
      subtitle: t(
        'adminGuidedSetup.steps.initialize.subtitle',
        "Let's cover the basics of your space so your agent starts with the right foundation."
      ),
    },
    {
      id: 'docs',
      label: t('adminGuidedSetup.steps.docs.label', 'Upload Docs'),
      icon: FileText,
      title: t('adminGuidedSetup.steps.docs.title', 'Upload your field guide'),
      subtitle: t(
        'adminGuidedSetup.steps.docs.subtitle',
        'Add the source material your agent answers from — books, guides, and reference documents.'
      ),
    },
    {
      id: 'resources',
      label: t('adminGuidedSetup.steps.resources.label', 'Curated Resources'),
      icon: Globe,
      title: t('adminGuidedSetup.steps.resources.title', 'Curated resources'),
      subtitle: t(
        'adminGuidedSetup.steps.resources.subtitle',
        'Add trusted real-world resources — key contacts, lawyers, educational and mental-health support — the agent can refer people to.'
      ),
    },
    {
      id: 'test',
      label: t('adminGuidedSetup.steps.test.label', 'Test as User'),
      icon: User,
      title: t('adminGuidedSetup.steps.test.title', 'Test as a user'),
      subtitle: t(
        'adminGuidedSetup.steps.test.subtitle',
        'Coming soon — try the assistant as one of your user types and rate the answers.'
      ),
      stub: true,
    },
    {
      id: 'feedback',
      label: t('adminGuidedSetup.steps.feedback.label', 'Feedback'),
      icon: MessageSquare,
      title: t('adminGuidedSetup.steps.feedback.title', 'Feedback loop'),
      subtitle: t(
        'adminGuidedSetup.steps.feedback.subtitle',
        'Coming soon — review answer quality and iterate on your setup.'
      ),
      stub: true,
    },
  ];

  // Index of the last built (navigable) step. Everything past it is locked.
  const lastBuilt = steps.reduce(
    (acc, step, index) => (step.stub ? acc : index),
    0
  );
  const step = steps[current];
  const StepIcon = step.icon;
  const isEnabled = (index: number) => !steps[index].stub;
  const onLastBuilt = current >= lastBuilt;

  return (
    <div className="flex h-screen flex-col bg-surface">
      {/* Progress path */}
      <header className="shrink-0 border-b border-border px-4 py-4 sm:px-6">
        <div className="mx-auto w-full max-w-5xl">
          <OnboardingWizardStepper
            steps={steps}
            current={current}
            isEnabled={isEnabled}
            onSelect={setCurrent}
          />
        </div>
      </header>

      {/* Active phase header: number + icon + title + subtitle */}
      <div className="shrink-0 border-b border-border px-4 py-5 sm:px-6">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-4">
          <div className="relative flex flex-none items-center gap-3 rounded-2xl border border-accent/30 bg-accent/10 px-4 py-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-bold text-accent-text">
              {current + 1}
            </span>
            <StepIcon className="h-6 w-6 text-accent" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-bold text-text">
              {step.title}
            </h1>
            <p className="mt-0.5 text-sm text-text-secondary">
              {step.subtitle}
            </p>
          </div>
        </div>
      </div>

      {/* Phase body */}
      <div className="min-h-0 flex-1">
        <Suspense
          fallback={
            <div className="flex h-full w-full items-center justify-center text-sm text-text-muted">
              {t('common.loading', 'Loading…')}
            </div>
          }
        >
          {step.id === 'initialize' ? (
            <div className="mx-auto h-full w-full max-w-3xl">
              <AdminConfigAssistant variant="sidebar" purpose="onboarding" />
            </div>
          ) : (
            <div className="h-full overflow-y-auto">
              <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
                {step.id === 'docs' && <AdminDocumentUpload embedded />}
                {step.id === 'resources' && (
                  <AdminResourcesDirectory embedded />
                )}
                {step.stub && (
                  <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-surface-raised px-6 py-16 text-center">
                    <StepIcon className="h-8 w-8 text-text-muted" />
                    <div className="text-base font-semibold text-text">
                      {step.title}
                    </div>
                    <p className="max-w-md text-sm text-text-secondary">
                      {t(
                        'adminGuidedSetup.comingSoon',
                        'This phase is coming soon and is being built separately.'
                      )}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </Suspense>
      </div>

      {/* Navigation */}
      <footer className="shrink-0 border-t border-border px-4 py-3 sm:px-6">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3">
          <Link
            to="/admin/setup"
            className="inline-flex items-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-text"
          >
            <Settings2 className="h-4 w-4" />
            {t('adminGuidedSetup.manual', 'Configure manually instead')}
          </Link>
          <div className="flex items-center gap-2">
            {current > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrent((c) => Math.max(0, c - 1))}
                leadingIcon={<ArrowLeft className="h-4 w-4" />}
              >
                {t('common.back', 'Back')}
              </Button>
            )}
            {onLastBuilt ? (
              <Link
                to="/admin/setup"
                className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-text shadow-sm transition-colors hover:bg-accent-hover"
              >
                <Sparkles className="h-4 w-4" />
                {t('adminGuidedSetup.finish', 'Finish & go to dashboard')}
              </Link>
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setCurrent((c) => Math.min(lastBuilt, c + 1))}
                trailingIcon={<ArrowRight className="h-4 w-4" />}
              >
                {t('common.continue', 'Continue')}
              </Button>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}
