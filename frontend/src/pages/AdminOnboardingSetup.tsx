import { lazy, Suspense } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowRight, Settings2, Sparkles } from 'lucide-react';

const AdminConfigAssistant = lazy(() =>
  import('../components/admin/AdminConfigAssistant').then((module) => ({
    default: module.AdminConfigAssistant,
  }))
);

/**
 * AI-facilitated first-run onboarding. Defaults to a chat-based setup that fills
 * most of the screen, with an obvious escape hatch to manual configuration.
 * The shared right-rail assistant is suppressed on this route (see AdminRoute)
 * so there is a single, primary assistant here.
 */
export function AdminOnboardingSetup() {
  const { t } = useTranslation();

  return (
    <div className="flex h-screen flex-col bg-surface">
      <header className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-accent" />
          <div>
            <h1 className="text-sm font-semibold text-text">
              {t('adminGuidedSetup.title', 'Set up your instance')}
            </h1>
            <p className="text-xs text-text-secondary">
              {t(
                'adminGuidedSetup.subtitle',
                'Your assistant will collect the basics in one pass.'
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/admin/setup"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text"
          >
            <Settings2 className="h-4 w-4" />
            {t('adminGuidedSetup.manual', 'Configure manually instead')}
          </Link>
          <Link
            to="/admin/setup"
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-text shadow-sm transition-colors hover:bg-accent-hover"
          >
            {t('adminGuidedSetup.finish', 'Finish & go to dashboard')}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-1 overflow-hidden">
        <Suspense
          fallback={
            <div className="flex h-full w-full items-center justify-center text-sm text-text-muted">
              {t('common.loading', 'Loading…')}
            </div>
          }
        >
          <AdminConfigAssistant variant="sidebar" purpose="onboarding" />
        </Suspense>
      </div>
    </div>
  );
}
