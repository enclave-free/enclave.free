import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Moon, Settings, Sun } from 'lucide-react';
import { useTheme } from '../../theme';
import { useInstanceConfig } from '../../context/InstanceConfigContext';
import { DynamicIcon } from './DynamicIcon';
import { SettingsDrawer } from './SettingsDrawer';
import { isAdminAuthenticated } from '../../utils/adminApi';
import { IconButton } from '../ui';
import { STORAGE_KEYS } from '../../types/onboarding';

interface AppHeaderProps {
  showBackButton?: boolean;
  backTo?: string;
  backLabel?: string;
  rightActions?: ReactNode;
  showSettings?: boolean;
}

function ThemeToggle() {
  const { t } = useTranslation();
  const { setTheme, resolvedTheme } = useTheme();

  return (
    <IconButton
      label={t('common.toggleTheme')}
      onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
      title={
        resolvedTheme === 'dark'
          ? t('common.switchToLight')
          : t('common.switchToDark')
      }
    >
      {resolvedTheme === 'dark' ? (
        <Sun className="h-4 w-4" aria-hidden="true" />
      ) : (
        <Moon className="h-4 w-4" aria-hidden="true" />
      )}
    </IconButton>
  );
}

export function AppHeader({
  showBackButton = false,
  backTo = '/',
  backLabel,
  rightActions,
  showSettings = true,
}: AppHeaderProps) {
  const { t } = useTranslation();
  const resolvedBackLabel = backLabel ?? t('common.back');
  const { config } = useInstanceConfig();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [logoError, setLogoError] = useState(false);
  const isAdmin = isAdminAuthenticated();
  const hasUserSession = Boolean(localStorage.getItem(STORAGE_KEYS.USER_EMAIL));
  const canOpenSettings = isAdmin || hasUserSession;
  const showIcon = config.headerLayout !== 'name_only';
  const showName = config.headerLayout !== 'icon_only';
  const showTagline = showName && Boolean(config.headerTagline?.trim());
  const hasLogoImage = Boolean(config.logoUrl?.trim()) && !logoError;
  const brandingBadgeClass = hasLogoImage
    ? 'bg-surface'
    : 'border border-border bg-surface-raised text-accent';

  useEffect(() => {
    setLogoError(false);
  }, [config.logoUrl]);

  return (
    <>
      <div className="max-w-5xl mx-auto px-3 sm:px-4 py-2.5 flex items-center justify-between border-b border-border/50">
        {/* Left: Back + Branding */}
        <div className="flex items-center gap-3">
          {showBackButton && (
            <Link
              to={backTo}
              className="btn btn-ghost focus-ring -ml-2 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
              title={resolvedBackLabel}
              aria-label={resolvedBackLabel}
            >
              <ArrowLeft className="h-5 w-5" aria-hidden="true" />
            </Link>
          )}
          <div className="flex items-center gap-2.5">
            {showIcon && (
              <div
                className={`w-8 h-8 rounded-lg ${brandingBadgeClass} flex items-center justify-center`}
              >
                {hasLogoImage ? (
                  <img
                    src={config.logoUrl}
                    alt={t('branding.logoAlt', '{{name}} logo', {
                      name: config.name,
                    })}
                    className="w-5 h-5 object-contain"
                    onError={() => setLogoError(true)}
                  />
                ) : (
                  <DynamicIcon
                    name={config.icon}
                    size={18}
                    className="text-accent"
                  />
                )}
              </div>
            )}
            {showName && (
              <div
                className={`${showIcon ? 'hidden sm:flex' : 'flex'} flex-col leading-tight`}
              >
                <span className="font-semibold text-text tracking-tight">
                  {config.name}
                </span>
                {showTagline && (
                  <span className="text-[11px] text-text-muted">
                    {config.headerTagline}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-1">
          {rightActions}

          {/* Settings gear - visible to signed-in users and admins */}
          {showSettings && canOpenSettings && (
            <IconButton
              label={t('common.settings')}
              onClick={() => setSettingsOpen(true)}
            >
              <Settings className="h-4 w-4" aria-hidden="true" />
            </IconButton>
          )}

          <ThemeToggle />
        </div>
      </div>

      {/* Settings Drawer */}
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </>
  );
}
