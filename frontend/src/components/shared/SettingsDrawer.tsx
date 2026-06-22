import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  Database,
  Gauge,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  Paintbrush,
  Server,
  Upload,
  UserCheck,
  Users,
  Wand2,
  X,
} from 'lucide-react';
import { useAuthFlow, clearAllAuth } from '../../hooks/useAuthFlow';
import { API_BASE } from '../../types/onboarding';

interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
}

interface SettingsLinkProps {
  to: string;
  icon: ReactNode;
  label: string;
  description?: string;
  onClick?: () => void;
}

function SettingsLink({
  to,
  icon,
  label,
  description,
  onClick,
}: SettingsLinkProps) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="group flex items-start gap-3 rounded-lg border border-transparent p-3 transition-all hover:border-border hover:bg-surface-overlay"
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-overlay text-text-secondary transition-all group-hover:bg-accent/10 group-hover:text-accent">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text transition-colors group-hover:text-accent">
          {label}
        </p>
        {description && (
          <p className="mt-0.5 text-xs leading-5 text-text-muted">
            {description}
          </p>
        )}
      </div>
    </Link>
  );
}

interface SettingsSection {
  label: string;
  items: SettingsLinkProps[];
}

function SettingsSectionView({ section }: { section: SettingsSection }) {
  return (
    <section aria-label={section.label}>
      <p className="label mb-3">{section.label}</p>
      <div className="space-y-1">
        {section.items.map((item) => (
          <SettingsLink key={item.to} {...item} />
        ))}
      </div>
    </section>
  );
}

export function SettingsDrawer({ open, onClose }: SettingsDrawerProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isAdmin, userEmail } = useAuthFlow();
  const drawerRef = useRef<HTMLDivElement>(null);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (open) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [open, onClose]);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    if (open) {
      // Delay to prevent immediate close from the button click
      setTimeout(() => {
        document.addEventListener('mousedown', handleClickOutside);
      }, 0);
      return () =>
        document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [open, onClose]);

  const handleSignOut = async () => {
    try {
      await Promise.all([
        fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          credentials: 'include',
        }),
        fetch(`${API_BASE}/admin/logout`, {
          method: 'POST',
          credentials: 'include',
        }),
      ]);
    } catch {
      // Best-effort logout
    }

    clearAllAuth();
    onClose();
    navigate('/login');
  };

  const adminSections: SettingsSection[] = [
    {
      label: t('settings.adminWorkflows', 'Admin Workflows'),
      items: [
        {
          to: '/admin/setup',
          onClick: onClose,
          label: t('settings.admin.instanceConfig', 'Admin Dashboard'),
          description: t(
            'settings.admin.instanceConfigDesc',
            'Return to the main admin dashboard.'
          ),
          icon: <LayoutDashboard className="h-4 w-4" aria-hidden="true" />,
        },
        {
          to: '/admin/onboarding',
          onClick: onClose,
          label: t('settings.admin.guidedSetup', 'Guided Setup'),
          description: t(
            'settings.admin.guidedSetupDesc',
            'Walk through setup, documents, resources, and testing.'
          ),
          icon: <Wand2 className="h-4 w-4" aria-hidden="true" />,
        },
        {
          to: '/admin/test-and-feedback',
          onClick: onClose,
          label: t('settings.admin.testUserSession', 'Test User Session'),
          description: t(
            'settings.admin.testUserSessionDesc',
            'Chat as a simulated user and review beta feedback.'
          ),
          icon: <UserCheck className="h-4 w-4" aria-hidden="true" />,
        },
      ],
    },
    {
      label: t('settings.settingsSection', 'Settings'),
      items: [
        {
          to: '/admin/instance',
          onClick: onClose,
          label: t('settings.admin.instanceBranding', 'Instance Settings'),
          description: t(
            'settings.admin.instanceBrandingDesc',
            'Name, public email identity, theme, and brand controls.'
          ),
          icon: <Paintbrush className="h-4 w-4" aria-hidden="true" />,
        },
        {
          to: '/admin/users',
          onClick: onClose,
          label: t('settings.admin.userConfig', 'User Settings'),
          description: t(
            'settings.admin.userConfigDesc',
            'User types and onboarding questions.'
          ),
          icon: <Users className="h-4 w-4" aria-hidden="true" />,
        },
        {
          to: '/admin/ai',
          onClick: onClose,
          label: t('settings.admin.aiConfig', 'Agent Settings'),
          description: t(
            'settings.admin.aiConfigDesc',
            'Prompts, model behavior, and document defaults.'
          ),
          icon: <Bot className="h-4 w-4" aria-hidden="true" />,
        },
      ],
    },
    {
      label: t('settings.dataAndContent', 'Data & Content'),
      items: [
        {
          to: '/admin/upload',
          onClick: onClose,
          label: t('settings.admin.documentUpload', 'Document Upload'),
          description: t(
            'settings.admin.documentUploadDesc',
            'Add documents to the knowledge base.'
          ),
          icon: <Upload className="h-4 w-4" aria-hidden="true" />,
        },
        {
          to: '/admin/resources',
          onClick: onClose,
          label: t('settings.admin.resourceDirectory', 'Resource Directory'),
          description: t(
            'settings.admin.resourceDirectoryDesc',
            'Manually curate trusted referral resources.'
          ),
          icon: <LifeBuoy className="h-4 w-4" aria-hidden="true" />,
        },
      ],
    },
    {
      label: t('settings.operations', 'Operations'),
      items: [
        {
          to: '/admin/database',
          onClick: onClose,
          label: t('settings.admin.databaseExplorer', 'Database Explorer'),
          description: t(
            'settings.admin.databaseExplorerDesc',
            'Review SQLite records, beta chat logs, and exports.'
          ),
          icon: <Database className="h-4 w-4" aria-hidden="true" />,
        },
        {
          to: '/admin/deployment',
          onClick: onClose,
          label: t('settings.admin.deploymentConfig', 'Deployment Settings'),
          description: t(
            'settings.admin.deploymentConfigDesc',
            'Runtime settings and service health.'
          ),
          icon: <Server className="h-4 w-4" aria-hidden="true" />,
        },
        {
          to: '/diagnostics/test-dashboard',
          onClick: onClose,
          label: t('settings.admin.diagnostics', 'Diagnostics'),
          description: t(
            'settings.admin.diagnosticsDesc',
            'Run smoke checks while investigating issues.'
          ),
          icon: <Gauge className="h-4 w-4" aria-hidden="true" />,
        },
      ],
    },
  ];

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 animate-fade-in" />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className="fixed right-0 top-0 h-full w-80 max-w-[90vw] bg-surface border-l border-border z-50 shadow-2xl animate-slide-in-right overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="heading-lg">{t('settings.title')}</h2>
          <button
            onClick={onClose}
            className="btn-ghost p-1.5 rounded-lg transition-all"
            aria-label={t('common.close')}
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-6">
          {/* User Info */}
          {userEmail && (
            <div className="pb-4 border-b border-border">
              <p className="label mb-2">{t('settings.signedInAs')}</p>
              <p className="text-sm font-medium text-text truncate">
                {userEmail}
              </p>
            </div>
          )}

          {isAdmin && (
            <>
              {adminSections.map((section) => (
                <SettingsSectionView key={section.label} section={section} />
              ))}
            </>
          )}

          {/* Sign Out */}
          <div className="pt-4 border-t border-border">
            <button
              onClick={handleSignOut}
              className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-error-subtle text-text-secondary hover:text-error transition-colors"
            >
              <div className="w-8 h-8 rounded-lg bg-surface-overlay flex items-center justify-center shrink-0">
                <LogOut className="h-4 w-4" aria-hidden="true" />
              </div>
              <span className="text-sm font-medium">
                {t('settings.signOut')}
              </span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
