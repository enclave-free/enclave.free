import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ArrowRight,
  BookOpen,
  Brain,
  Database,
  LifeBuoy,
  MessageCircle,
  Paintbrush,
  Server,
  Sparkles,
  Upload,
  UserCheck,
  Users,
  Wand2,
} from 'lucide-react';
import { InstanceLogo } from '../components/shared/InstanceLogo';
import { isAdminAuthenticated } from '../utils/adminApi';

interface DashboardCardProps {
  to: string;
  icon: ReactNode;
  title: string;
  description: string;
}

function DashboardCard({ to, icon, title, description }: DashboardCardProps) {
  return (
    <Link
      to={to}
      className="card card-sm bg-surface-raised card-interactive group flex min-h-[5.25rem] items-center gap-4"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent transition-colors group-hover:bg-accent/20">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-text-muted">
          {description}
        </p>
      </div>
      <ArrowRight className="h-4 w-4 shrink-0 text-text-muted transition-all group-hover:translate-x-0.5 group-hover:text-accent" />
    </Link>
  );
}

function DashboardSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="mb-8">
      <div className="label mb-3">{title}</div>
      <div className="grid gap-4 sm:grid-cols-2">{children}</div>
    </section>
  );
}

export function AdminSetup() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    if (!isAdminAuthenticated()) {
      navigate('/');
    } else {
      setAuthChecked(true);
    }
  }, [navigate]);

  if (!authChecked) return null;

  return (
    <div className="flex min-h-screen flex-col items-center bg-surface p-6 md:p-10">
      <div className="w-full max-w-5xl">
        <InstanceLogo />

        <div className="mb-10 text-center animate-fade-in-up">
          <h1 className="heading-xl">
            {t('adminDashboard.title', 'Admin Dashboard')}
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            {t(
              'adminDashboard.subtitleSimple',
              'Choose where you want to work on this instance.'
            )}
          </p>
        </div>

        <DashboardSection
          title={t('adminDashboard.workflowsSectionLabel', 'Admin Workflows')}
        >
          <DashboardCard
            to="/chat"
            icon={<MessageCircle className="h-5 w-5" />}
            title={t('adminDashboard.adminAssistant', 'Admin Assistant')}
            description={t(
              'adminDashboard.adminAssistantDesc',
              'Use the admin chat for configuration help and change review.'
            )}
          />
          <DashboardCard
            to="/admin/onboarding"
            icon={<Wand2 className="h-5 w-5" />}
            title={t('adminDashboard.guidedSetup', 'Guided Setup')}
            description={t(
              'adminDashboard.guidedSetupDesc',
              'Walk through setup, documents, resources, and testing.'
            )}
          />
          <DashboardCard
            to="/admin/guides"
            icon={<BookOpen className="h-5 w-5" />}
            title={t('adminDashboard.guides', 'Admin Guides')}
            description={t(
              'adminDashboard.guidesDesc',
              'Simple setup steps for first-time admins.'
            )}
          />
          <DashboardCard
            to="/admin/test-and-feedback"
            icon={<UserCheck className="h-5 w-5" />}
            title={t('adminDashboard.testUserSession', 'Test User Session')}
            description={t(
              'adminDashboard.testUserSessionDesc',
              'Chat as a simulated user and review saved beta logs.'
            )}
          />
        </DashboardSection>

        <DashboardSection
          title={t('adminDashboard.settingsSectionLabel', 'Settings')}
        >
          <DashboardCard
            to="/admin/instance"
            icon={<Paintbrush className="h-5 w-5" />}
            title={t('adminDashboard.instance', 'Instance Settings')}
            description={t(
              'adminDashboard.instanceDescSimple',
              'Name, public email identity, theme, and brand controls.'
            )}
          />
          <DashboardCard
            to="/admin/users"
            icon={<Users className="h-5 w-5" />}
            title={t('adminDashboard.user', 'User Settings')}
            description={t(
              'adminDashboard.userDesc',
              'Define user types and onboarding questions.'
            )}
          />
          <DashboardCard
            to="/admin/ai"
            icon={<Brain className="h-5 w-5" />}
            title={t('adminDashboard.ai', 'Agent Settings')}
            description={t(
              'adminDashboard.aiDescSimple',
              'Prompts, model behavior, and document defaults.'
            )}
          />
        </DashboardSection>

        <DashboardSection
          title={t('adminDashboard.dataSectionLabel', 'Data & Content')}
        >
          <DashboardCard
            to="/admin/upload"
            icon={<Upload className="h-5 w-5" />}
            title={t('adminDashboard.upload', 'Document Upload')}
            description={t(
              'adminDashboard.uploadDesc',
              'Add documents to the knowledge base.'
            )}
          />
          <DashboardCard
            to="/admin/resources"
            icon={<LifeBuoy className="h-5 w-5" />}
            title={t('adminDashboard.resources', 'Resource Directory')}
            description={t(
              'adminDashboard.resourcesDescSimple',
              'Manually curate trusted referral resources.'
            )}
          />
        </DashboardSection>

        <DashboardSection
          title={t('adminDashboard.operationsSectionLabel', 'Operations')}
        >
          <DashboardCard
            to="/admin/deployment"
            icon={<Server className="h-5 w-5" />}
            title={t('adminDashboard.deployment', 'Deployment Settings')}
            description={t(
              'adminDashboard.deploymentDescSimple',
              'Runtime settings, health, and readiness details.'
            )}
          />
          <DashboardCard
            to="/admin/database"
            icon={<Database className="h-5 w-5" />}
            title={t('adminDashboard.database', 'Database Explorer')}
            description={t(
              'adminDashboard.databaseDesc',
              'Browse and query the SQLite database.'
            )}
          />
          <DashboardCard
            to="/diagnostics/test-dashboard"
            icon={<Sparkles className="h-5 w-5" />}
            title={t('adminDashboard.testDashboard', 'Diagnostics')}
            description={t(
              'adminDashboard.testDashboardDescSimple',
              'Run smoke checks when investigating a problem.'
            )}
          />
        </DashboardSection>
      </div>
    </div>
  );
}
