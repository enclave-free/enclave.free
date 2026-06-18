import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Clock, LogOut } from 'lucide-react';
import { OnboardingCard } from '../components/onboarding/OnboardingCard';
import { Button } from '../components/ui';
import {
  API_BASE,
  STORAGE_KEYS,
  clearSelectedUserTypeId,
  saveSelectedUserTypeId,
} from '../types/onboarding';

export function PendingApproval() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const email = localStorage.getItem(STORAGE_KEYS.USER_EMAIL);

  useEffect(() => {
    let cancelled = false;

    async function refreshApprovalStatus() {
      try {
        const response = await fetch(`${API_BASE}/auth/me`, {
          credentials: 'include',
        });

        if (cancelled || !response.ok) return;

        const data = await response.json();
        const user = data?.user;

        if (!data?.authenticated || !user) return;

        localStorage.setItem(
          STORAGE_KEYS.USER_APPROVED,
          String(user.approved !== false)
        );

        if (user.user_type_id !== null && user.user_type_id !== undefined) {
          saveSelectedUserTypeId(user.user_type_id);
        } else {
          clearSelectedUserTypeId();
        }

        if (user.approved === false) return;

        if (cancelled) return;

        if (user.needs_user_type) {
          navigate('/user-type');
        } else if (user.needs_onboarding) {
          navigate('/profile');
        } else {
          navigate('/chat');
        }
      } catch {
        // Stay on the pending screen if the status check fails.
      }
    }

    void refreshApprovalStatus();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // Best-effort logout
    }

    // Clear all user data
    localStorage.removeItem(STORAGE_KEYS.SESSION_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER_EMAIL);
    localStorage.removeItem(STORAGE_KEYS.USER_NAME);
    localStorage.removeItem(STORAGE_KEYS.USER_APPROVED);
    localStorage.removeItem(STORAGE_KEYS.USER_PROFILE);
    localStorage.removeItem(STORAGE_KEYS.USER_TYPE_ID);
    navigate('/auth');
  };

  return (
    <OnboardingCard title={t('onboarding.pending.title')}>
      <div className="text-center py-8 animate-fade-in">
        <div className="w-16 h-16 bg-warning/10 rounded-full flex items-center justify-center mx-auto mb-6">
          <Clock className="w-8 h-8 text-warning" />
        </div>
        <h2 className="text-xl font-semibold text-text mb-2">
          {t('onboarding.pending.heading')}
        </h2>
        <p className="text-sm text-text-muted mb-4">
          {t('onboarding.pending.message')}
        </p>
        {email && (
          <p className="inline-block bg-surface-overlay px-4 py-2 rounded-lg text-sm font-medium text-text mb-6">
            {email}
          </p>
        )}
        <p className="text-xs text-text-muted mb-6">
          {t('onboarding.pending.checkBack')}
        </p>
        <Button
          onClick={handleLogout}
          variant="ghost"
          size="md"
          leadingIcon={<LogOut className="w-4 h-4" aria-hidden="true" />}
        >
          {t('common.logout')}
        </Button>
      </div>
    </OnboardingCard>
  );
}
