import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { OnboardingCard } from '../components/onboarding/OnboardingCard';
import { Button } from '../components/ui';
import {
  STORAGE_KEYS,
  API_BASE,
  saveSelectedUserTypeId,
  clearSelectedUserTypeId,
} from '../types/onboarding';
import { clearLogoutBrowserStorage } from '../utils/browserStoragePosture';

type VerifyState = 'verifying' | 'success' | 'error';

type VerifiedMagicLinkResponse = {
  user: {
    email: string;
    name?: string | null;
    user_type_id?: number | null;
    approved?: boolean;
    needs_onboarding?: boolean;
    needs_user_type?: boolean;
  };
};

const verificationRequestsByToken = new Map<
  string,
  Promise<VerifiedMagicLinkResponse>
>();

function verifyMagicLinkTokenOnce(
  token: string,
  fallbackErrorMessage: string
): Promise<VerifiedMagicLinkResponse> {
  const existing = verificationRequestsByToken.get(token);
  if (existing) return existing;

  const request = (async () => {
    const response = await fetch(`${API_BASE}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ token }),
    });

    if (!response.ok) {
      let errorMessage = fallbackErrorMessage;
      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const error = await response.json();
          errorMessage = error.detail || error.message || errorMessage;
        } else {
          const text = await response.text();
          errorMessage = text || errorMessage;
        }
      } catch {
        errorMessage = response.statusText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    return response.json();
  })();

  verificationRequestsByToken.set(token, request);
  void request
    .finally(() => {
      verificationRequestsByToken.delete(token);
    })
    .catch(() => undefined);
  return request;
}

export function VerifyMagicLink() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const [state, setState] = useState<VerifyState>('verifying');
  const [email, setEmail] = useState<string | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [needsUserType, setNeedsUserType] = useState(false);
  const [isApproved, setIsApproved] = useState(true);
  const hasVerified = useRef(false); // Prevent double-execution in StrictMode

  useEffect(() => {
    let active = true;
    const token = searchParams.get('token');

    async function inferOnboardingNeeds() {
      try {
        const [typesRes, fieldsRes] = await Promise.all([
          fetch(`${API_BASE}/user-types`),
          fetch(`${API_BASE}/user-fields`),
        ]);

        const typesData = typesRes.ok ? await typesRes.json() : { types: [] };
        const fieldsData = fieldsRes.ok
          ? await fieldsRes.json()
          : { fields: [] };

        const typeCount = typesData.types?.length || 0;
        if (typeCount === 1 && typesData.types?.[0]?.id !== undefined) {
          saveSelectedUserTypeId(typesData.types[0].id);
        }

        const hasTypes = (typesData.types?.length || 0) > 1;
        const hasFields = (fieldsData.fields?.length || 0) > 0;
        if (!active) return;
        setNeedsUserType(hasTypes);
        setNeedsOnboarding(hasTypes || hasFields);
      } catch {
        if (!active) return;
        setNeedsUserType(false);
        setNeedsOnboarding(false);
      }
    }

    async function hydrateSingleUserType() {
      try {
        const typesRes = await fetch(`${API_BASE}/user-types`);
        const typesData = typesRes.ok ? await typesRes.json() : { types: [] };
        const typeCount = typesData.types?.length || 0;
        if (typeCount === 1 && typesData.types?.[0]?.id !== undefined) {
          saveSelectedUserTypeId(typesData.types[0].id);
        }
      } catch {
        // Ignore if we can't hydrate user type
      }
    }

    async function verifyToken() {
      // Prevent double-execution in React StrictMode
      if (hasVerified.current) {
        return;
      }

      if (!token) {
        setState('error');
        return;
      }

      try {
        const data = await verifyMagicLinkTokenOnce(
          token,
          t('errors.verificationFailed')
        );
        if (!active) return;

        if (
          data.user?.user_type_id !== null &&
          data.user?.user_type_id !== undefined
        ) {
          saveSelectedUserTypeId(data.user.user_type_id);
        } else {
          clearSelectedUserTypeId();
        }

        const onboardingFlag =
          typeof data.user?.needs_onboarding === 'boolean'
            ? data.user.needs_onboarding
            : null;
        const userTypeFlag =
          typeof data.user?.needs_user_type === 'boolean'
            ? data.user.needs_user_type
            : null;

        if (onboardingFlag === null || userTypeFlag === null) {
          await inferOnboardingNeeds();
        } else {
          setNeedsOnboarding(onboardingFlag);
          setNeedsUserType(userTypeFlag);
          if (
            onboardingFlag &&
            !userTypeFlag &&
            (data.user?.user_type_id === null ||
              data.user?.user_type_id === undefined)
          ) {
            await hydrateSingleUserType();
          }
        }

        // A user session must not inherit stale admin routing markers from a
        // previous browser session. The server cookie remains authoritative.
        clearLogoutBrowserStorage('admin');

        // Store user info (session is maintained in secure cookie)
        localStorage.setItem(STORAGE_KEYS.USER_EMAIL, data.user.email);
        if (data.user.name) {
          localStorage.setItem(STORAGE_KEYS.USER_NAME, data.user.name);
        } else {
          localStorage.removeItem(STORAGE_KEYS.USER_NAME);
        }

        // Store approval status
        const approved = data.user.approved !== false;
        localStorage.setItem(STORAGE_KEYS.USER_APPROVED, String(approved));
        setIsApproved(approved);

        // Clean up pending state
        localStorage.removeItem(STORAGE_KEYS.PENDING_EMAIL);
        localStorage.removeItem(STORAGE_KEYS.PENDING_NAME);

        setEmail(data.user.email);
        setName(data.user.name ?? null);
        hasVerified.current = true;
        setState('success');
      } catch (error) {
        if (active) {
          console.error('Verification error:', error);
          setState('error');
        }
      }
    }

    verifyToken();

    return () => {
      active = false;
    };
  }, [searchParams, t]);

  useEffect(() => {
    // Redirect after success
    if (state === 'success') {
      const redirectTimer = setTimeout(() => {
        // If not approved, go to pending page
        if (!isApproved) {
          navigate('/pending');
        } else if (needsOnboarding) {
          // If onboarding needed, go to user-type selection (which auto-skips if needed)
          if (needsUserType) {
            navigate('/user-type');
          } else {
            navigate('/profile');
          }
        } else {
          navigate('/chat');
        }
      }, 2500);

      return () => clearTimeout(redirectTimer);
    }
  }, [state, navigate, needsOnboarding, needsUserType, isApproved]);

  return (
    <OnboardingCard>
      {/* Verifying State */}
      {state === 'verifying' && (
        <div className="text-center py-8 animate-fade-in">
          <div className="w-12 h-12 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-6" />
          <h2 className="text-lg font-semibold text-text mb-2">
            {t('onboarding.verify.verifying')}
          </h2>
          <p className="text-sm text-text-muted">
            {t('onboarding.verify.pleaseWait')}
          </p>
        </div>
      )}

      {/* Success State */}
      {state === 'success' && (
        <div className="text-center py-8 animate-fade-in">
          <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg
              className="w-8 h-8 text-success"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-text mb-2">
            {name
              ? t('onboarding.verify.welcomeName', { name })
              : t('onboarding.verify.welcomeBack')}
          </h2>
          <p className="text-sm text-text-muted mb-4">
            {t('onboarding.verify.signedInAs')}
          </p>
          <p className="inline-block bg-surface-overlay px-4 py-2 rounded-lg text-sm font-medium text-text">
            {email}
          </p>
          <p className="text-xs text-text-muted mt-6">
            {needsOnboarding
              ? t('onboarding.verify.completingProfile')
              : t('onboarding.verify.redirectingChat')}
          </p>
        </div>
      )}

      {/* Error State */}
      {state === 'error' && (
        <div className="text-center py-8 animate-fade-in">
          <div className="w-16 h-16 bg-error/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg
              className="w-8 h-8 text-error"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-text mb-2">
            {t('onboarding.verify.linkExpired')}
          </h2>
          <p className="text-sm text-text-muted mb-6">
            {t('onboarding.verify.linkExpiredMessage')}
          </p>
          <Button onClick={() => navigate('/login')} size="lg">
            {t('onboarding.verify.requestNewLink')}
          </Button>
        </div>
      )}
    </OnboardingCard>
  );
}
