import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  FileText,
  LifeBuoy,
  Server,
  ShieldCheck,
  Upload,
  UserCheck,
  Users,
  Wand2,
} from 'lucide-react';
import { Card, PageShell, SectionHeader } from '../components/ui';

interface Step {
  title: string;
  body: string;
}

interface GuideLink {
  to: string;
  title: string;
  body: string;
  icon: JSX.Element;
}

const quickSteps: Step[] = [
  {
    title: 'Sign in as admin',
    body: 'Use the admin login key. Keep it private.',
  },
  {
    title: 'Run Guided Setup',
    body: 'Tell Enclave what this instance is for.',
  },
  {
    title: 'Add useful content',
    body: 'Upload trusted docs and add real resources.',
  },
  {
    title: 'Test like a user',
    body: 'Ask real questions before inviting people.',
  },
  {
    title: 'Approve new users',
    body: 'Review signups in User Settings.',
  },
];

const safetyBasics = [
  'Review every change before clicking Apply.',
  'Leave secret sharing off unless you are debugging.',
  'Keep admin login keys out of chat, email, and tickets.',
  'Check Deployment Settings after big config changes.',
];

export function AdminGuides() {
  const { t } = useTranslation();

  const guideLinks: GuideLink[] = [
    {
      to: '/admin/onboarding',
      title: t('adminGuides.links.guidedSetup.title', 'Guided Setup'),
      body: t(
        'adminGuides.links.guidedSetup.body',
        'Start here. Set the name, users, questions, docs, and resources.'
      ),
      icon: <Wand2 className="h-5 w-5" />,
    },
    {
      to: '/admin/users',
      title: t('adminGuides.links.users.title', 'User Settings'),
      body: t(
        'adminGuides.links.users.body',
        'Choose user types, onboarding questions, and approvals.'
      ),
      icon: <Users className="h-5 w-5" />,
    },
    {
      to: '/admin/upload',
      title: t('adminGuides.links.upload.title', 'Document Upload'),
      body: t(
        'adminGuides.links.upload.body',
        'Add the PDFs, policies, FAQs, and guides the agent should know.'
      ),
      icon: <Upload className="h-5 w-5" />,
    },
    {
      to: '/admin/resources',
      title: t('adminGuides.links.resources.title', 'Resource Directory'),
      body: t(
        'adminGuides.links.resources.body',
        'Add trusted links, contacts, services, and referrals.'
      ),
      icon: <LifeBuoy className="h-5 w-5" />,
    },
    {
      to: '/admin/test-and-feedback',
      title: t('adminGuides.links.test.title', 'Test User Session'),
      body: t(
        'adminGuides.links.test.body',
        'Try the instance as a user and find confusing answers early.'
      ),
      icon: <UserCheck className="h-5 w-5" />,
    },
    {
      to: '/admin/deployment',
      title: t('adminGuides.links.deployment.title', 'Deployment Settings'),
      body: t(
        'adminGuides.links.deployment.body',
        'Check health, model settings, email, URLs, and readiness.'
      ),
      icon: <Server className="h-5 w-5" />,
    },
  ];

  return (
    <PageShell
      width="lg"
      className="bg-surface"
      header={
        <div className="flex flex-col gap-4">
          <Link
            to="/admin/setup"
            className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text"
          >
            <ArrowLeft className="h-4 w-4" />
            {t('common.backToAdminDashboard', 'Back to Admin Dashboard')}
          </Link>
          <SectionHeader
            icon={<BookOpen className="h-5 w-5" />}
            title={t('adminGuides.title', 'Admin Guides')}
            description={t(
              'adminGuides.subtitle',
              'Simple steps for setting up and running this instance.'
            )}
          />
        </div>
      }
    >
      <section className="flex flex-col gap-4" aria-labelledby="quick-start">
        <div className="flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
          <div>
            <h2 id="quick-start" className="text-base font-semibold text-text">
              {t('adminGuides.quickStart.title', 'Start with this')}
            </h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              {t(
                'adminGuides.quickStart.body',
                'Get to a small useful setup first. Improve it after testing.'
              )}
            </p>
          </div>
        </div>

        <ol className="grid gap-3 md:grid-cols-5">
          {quickSteps.map((step, index) => (
            <li
              key={step.title}
              className="rounded-lg border border-border bg-surface-raised p-4"
            >
              <div className="text-xs font-semibold uppercase tracking-normal text-accent">
                {t('adminGuides.stepLabel', 'Step')} {index + 1}
              </div>
              <h3 className="mt-2 text-sm font-semibold text-text">
                {t(`adminGuides.quickSteps.${index}.title`, step.title)}
              </h3>
              <p className="mt-1 text-xs leading-5 text-text-secondary">
                {t(`adminGuides.quickSteps.${index}.body`, step.body)}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="where-to-go">
        <div className="flex items-start gap-2">
          <FileText className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
          <div>
            <h2 id="where-to-go" className="text-base font-semibold text-text">
              {t('adminGuides.whereToGo.title', 'Where to go')}
            </h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              {t(
                'adminGuides.whereToGo.body',
                'Use these pages for the common admin jobs.'
              )}
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {guideLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="card card-sm bg-surface-raised card-interactive group flex min-h-[6rem] items-start gap-4"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent transition-colors group-hover:bg-accent/20">
                {link.icon}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-text">
                  {link.title}
                </h3>
                <p className="mt-1 text-xs leading-5 text-text-secondary">
                  {link.body}
                </p>
              </div>
              <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-text-muted transition-all group-hover:translate-x-0.5 group-hover:text-accent" />
            </Link>
          ))}
        </div>
      </section>

      <Card>
        <div className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
          <div>
            <h2 className="text-base font-semibold text-text">
              {t('adminGuides.safety.title', 'Safety basics')}
            </h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              {t(
                'adminGuides.safety.body',
                'Admins control access, data, and setup. Go slow with risky changes.'
              )}
            </p>
          </div>
        </div>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {safetyBasics.map((item, index) => (
            <li
              key={item}
              className="flex items-start gap-2 text-sm leading-6 text-text-secondary"
            >
              <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-success" />
              <span>{t(`adminGuides.safety.items.${index}`, item)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </PageShell>
  );
}
