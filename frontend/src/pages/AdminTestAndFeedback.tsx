import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, MessageSquare, UserCheck } from 'lucide-react';
import { PageShell, SectionHeader } from '../components/ui';
import { TestAsUserView } from '../components/admin/testfeedback/TestAsUserView';
import { FeedbackView } from '../components/admin/testfeedback/FeedbackView';

type TestFeedbackTab = 'test' | 'feedback';

/**
 * Test & Feedback — the ongoing refinement loop that lives outside first-run
 * onboarding. Two modes the admin can switch between at will:
 *   - Test as User: impersonate a non-admin test user and chat as them.
 *   - Feedback: review saved trial transcripts and rate each turn.
 *
 * Reachable any time from the dashboard, and the destination first-run
 * onboarding hands off to once the 3 setup steps are done.
 *
 * NOTE: scaffold. The Test-as-User chat (impersonation seam) and the Feedback
 * transcript review are wired in subsequent slices once the trials backend and
 * the impersonation script land.
 */
export function AdminTestAndFeedback() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TestFeedbackTab>('test');

  const tabs: { id: TestFeedbackTab; label: string }[] = [
    { id: 'test', label: t('adminTestFeedback.tabs.test', 'Test as User') },
    {
      id: 'feedback',
      label: t('adminTestFeedback.tabs.feedback', 'Feedback'),
    },
  ];

  return (
    <PageShell
      width="lg"
      header={
        <div className="flex flex-col gap-4">
          <Link
            to="/admin/setup"
            className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text"
          >
            <ArrowLeft className="h-4 w-4" />
            {t('common.backToAdmin', 'Back to Admin')}
          </Link>
          <SectionHeader
            title={
              <span className="inline-flex items-center gap-2">
                <UserCheck className="h-5 w-5" />
                {t('adminTestFeedback.title', 'Test & Feedback')}
              </span>
            }
            description={t(
              'adminTestFeedback.subtitle',
              'Try the assistant as one of your user types, then review the transcript and rate each answer to refine your setup.'
            )}
          />
          <div
            role="tablist"
            className="inline-flex gap-1 rounded-xl border border-border bg-surface-raised p-1"
          >
            {tabs.map((entry) => {
              const active = entry.id === tab;
              return (
                <button
                  key={entry.id}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setTab(entry.id)}
                  className={[
                    'rounded-lg px-4 py-1.5 text-sm font-medium transition-colors',
                    active
                      ? 'bg-accent text-accent-text shadow-sm'
                      : 'text-text-secondary hover:bg-surface-overlay hover:text-text',
                  ].join(' ')}
                >
                  {entry.id === 'test' ? (
                    <span className="inline-flex items-center gap-1.5">
                      <UserCheck className="h-4 w-4" />
                      {entry.label}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5">
                      <MessageSquare className="h-4 w-4" />
                      {entry.label}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      }
    >
      {tab === 'test' ? (
        <TestAsUserView onSaved={() => setTab('feedback')} />
      ) : (
        <FeedbackView />
      )}
    </PageShell>
  );
}
