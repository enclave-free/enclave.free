import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2, Mail, ShieldCheck, Lock, Timer } from 'lucide-react'
import { OnboardingCard } from '../components/onboarding/OnboardingCard'
import { LanguageSwitcher } from '../components/onboarding/LanguageSwitcher'
import { Button, Callout, TextField } from '../components/ui'
import { API_BASE, STORAGE_KEYS } from '../types/onboarding'
import { useInstanceConfig } from '../context/InstanceConfigContext'
import { getExplicitLanguageChoice } from '../utils/languages'

type TabType = 'signup' | 'login'
type FormState = 'idle' | 'submitting' | 'success' | 'error'

interface FormData {
  name: string
  email: string
}

function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

function TabSwitcher({
  activeTab,
  onTabChange,
  signUpLabel,
  logInLabel,
}: {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
  signUpLabel: string
  logInLabel: string
}) {
  return (
    <div className="flex min-w-0 bg-surface-overlay rounded-xl p-1.5 mb-6">
      <button
        onClick={() => onTabChange('signup')}
        className={`min-w-0 flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
          activeTab === 'signup'
            ? 'bg-surface text-text shadow-md'
            : 'text-text-muted hover:text-text'
        }`}
      >
        {signUpLabel}
      </button>
      <button
        onClick={() => onTabChange('login')}
        className={`min-w-0 flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
          activeTab === 'login'
            ? 'bg-surface text-text shadow-md'
            : 'text-text-muted hover:text-text'
        }`}
      >
        {logInLabel}
      </button>
    </div>
  )
}

function InputField({
  label,
  type,
  value,
  onChange,
  placeholder,
  required,
  error,
}: {
  label: string
  type: string
  value: string
  onChange: (value: string) => void
  placeholder: string
  required?: boolean
  error?: string
}) {
  return (
    <TextField
      label={label}
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      error={error}
    />
  )
}

interface SuccessMessageProps {
  email: string
  checkEmailTitle: string
  sentMagicLink: string
  clickLink: string
  checkSpam: string
}

function SuccessMessage({
  email,
  checkEmailTitle,
  sentMagicLink,
  clickLink,
  checkSpam,
}: SuccessMessageProps) {
  return (
    <div className="text-center py-6 animate-fade-in">
      <div className="w-16 h-16 bg-success/10 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg ring-1 ring-success/20">
        <Mail className="w-8 h-8 text-success" />
      </div>
      <h3 className="heading-lg mb-2">{checkEmailTitle}</h3>
      <p className="text-sm text-text-muted mb-4">{sentMagicLink}</p>
      <p className="inline-block bg-surface-overlay px-5 py-2.5 rounded-xl text-sm font-medium text-text border border-border">
        {email}
      </p>
      <p className="text-xs text-text-muted mt-4">
        {clickLink}
        <br />
        {checkSpam}
      </p>
    </div>
  )
}

export function UserAuth() {
  const { t } = useTranslation()
  const { config } = useInstanceConfig()
  const [activeTab, setActiveTab] = useState<TabType>('signup')
  const [formState, setFormState] = useState<FormState>('idle')
  const [formData, setFormData] = useState<FormData>({ name: '', email: '' })
  const [errors, setErrors] = useState<Partial<FormData>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submittedEmail, setSubmittedEmail] = useState<string>('')

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab)
    setErrors({})
    setFormError(null)
    setFormState('idle')
  }

  const validate = (): boolean => {
    const newErrors: Partial<FormData> = {}

    if (activeTab === 'signup' && !formData.name.trim()) {
      newErrors.name = t('onboarding.auth.nameRequired')
    }

    if (!formData.email.trim()) {
      newErrors.email = t('onboarding.auth.emailRequired')
    } else if (!validateEmail(formData.email)) {
      newErrors.email = t('onboarding.auth.emailInvalid')
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    if (!validate()) return

    setFormState('submitting')
    setFormError(null)

    try {
      // Call the magic link API
      const locale = getExplicitLanguageChoice()
      const response = await fetch(`${API_BASE}/auth/magic-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: formData.email,
          name: activeTab === 'signup' ? formData.name : '',
          ...(locale ? { locale } : {}),
        }),
      })

      if (!response.ok) {
        let errorMessage = t('errors.failedToSendMagicLink')
        try {
          const contentType = response.headers.get('content-type')
          if (contentType && contentType.includes('application/json')) {
            const error = await response.json()
            errorMessage = error.detail || error.message || errorMessage
          } else {
            const text = await response.text()
            errorMessage = text || errorMessage
          }
        } catch (parseError) {
          // If JSON parsing fails, use status text or default message
          errorMessage = response.statusText || errorMessage
        }
        throw new Error(errorMessage)
      }

      // Store email for verification page
      localStorage.setItem(STORAGE_KEYS.PENDING_EMAIL, formData.email)
      if (activeTab === 'signup') {
        localStorage.setItem(STORAGE_KEYS.PENDING_NAME, formData.name)
      }

      setSubmittedEmail(formData.email)
      setFormState('success')
    } catch (error) {
      console.error('Magic link error:', error)
      setFormError(error instanceof Error ? error.message : t('errors.failedToSendMagicLink'))
      setFormState('error')
    }
  }

  const footer = (
    <>
      <span>{t('common.adminQuestion')} </span>
      <Link to="/admin" className="text-accent hover:text-accent-hover font-medium transition-colors">
        {t('common.signInNostr')}
      </Link>
    </>
  )

  const title = activeTab === 'signup'
    ? t('onboarding.auth.createAccountTitle')
    : t('onboarding.auth.welcomeBackTitle')
  const subtitle = activeTab === 'signup'
    ? t('onboarding.auth.createAccountSubtitle', { instanceName: config.name })
    : t('onboarding.auth.welcomeBackSubtitle')

  return (
    <OnboardingCard
      topRight={<LanguageSwitcher />}
      title={title}
      subtitle={subtitle}
      footer={footer}
    >
      {formState === 'success' ? (
        <SuccessMessage
          email={submittedEmail}
          checkEmailTitle={t('onboarding.auth.checkEmail')}
          sentMagicLink={t('onboarding.auth.sentMagicLink')}
          clickLink={t('onboarding.auth.clickLink')}
          checkSpam={t('onboarding.auth.checkSpam')}
        />
      ) : (
        <>
          <TabSwitcher
            activeTab={activeTab}
            onTabChange={handleTabChange}
            signUpLabel={t('onboarding.auth.signUp')}
            logInLabel={t('onboarding.auth.logIn')}
          />

          <form onSubmit={handleSubmit} className="space-y-4">
            {formState === 'error' && formError && (
              <Callout
                label={t('onboarding.auth.errorLabel', 'Magic link request error')}
                tone="error"
              >
                {formError}
              </Callout>
            )}

            {activeTab === 'signup' && (
              <InputField
                label={t('onboarding.auth.nameLabel')}
                type="text"
                value={formData.name}
                onChange={(name) => {
                  setFormData((prev) => ({ ...prev, name }))
                  setFormError(null)
                  setFormState('idle')
                  if (errors.name) setErrors((prev) => ({ ...prev, name: undefined }))
                }}
                placeholder={t('onboarding.auth.namePlaceholder')}
                required
                error={errors.name}
              />
            )}

            <InputField
              label={t('onboarding.auth.emailLabel')}
              type="email"
              value={formData.email}
              onChange={(email) => {
                setFormData((prev) => ({ ...prev, email }))
                setFormError(null)
                setFormState('idle')
                if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }))
              }}
              placeholder={t('onboarding.auth.emailPlaceholder')}
              required
              error={errors.email}
            />

            <Button
              type="submit"
              disabled={formState === 'submitting'}
              className="w-full mt-6"
              size="lg"
              leadingIcon={
                formState === 'submitting'
                  ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  : <Mail className="w-5 h-5" aria-hidden="true" />
              }
            >
              {formState === 'submitting'
                ? t('onboarding.auth.sendingLink')
                : t('onboarding.auth.continueWithEmail')}
            </Button>

            <p className="text-xs text-text-muted text-center mt-4">
              {t('onboarding.auth.magicLinkHelp')}
            </p>

            <div className="rounded-xl border border-border bg-surface-overlay p-4 mt-3">
              <div className="flex items-center gap-2 mb-3">
                <ShieldCheck className="w-4 h-4 text-accent shrink-0" />
                <h3 className="text-sm font-semibold text-text">
                  {t('onboarding.auth.dataProtectionTitle')}
                </h3>
              </div>

              <div className="space-y-3">
                <div className="flex gap-2.5">
                  <Lock className="w-4 h-4 text-text-muted mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-text">{t('onboarding.auth.noPasswordTitle')}</p>
                    <p className="text-xs text-text-muted">{t('onboarding.auth.noPasswordBody')}</p>
                  </div>
                </div>

                <div className="flex gap-2.5">
                  <Timer className="w-4 h-4 text-text-muted mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-text">{t('onboarding.auth.expiringLinkTitle')}</p>
                    <p className="text-xs text-text-muted">{t('onboarding.auth.expiringLinkBody')}</p>
                  </div>
                </div>

                <div className="flex gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-text-muted mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-text">{t('onboarding.auth.encryptionTitle')}</p>
                    <p className="text-xs text-text-muted">{t('onboarding.auth.encryptionBody')}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-surface p-3">
              <p className="text-xs text-text-muted leading-relaxed">
                {t('onboarding.auth.adminControlNotice')}
              </p>
              <p className="text-xs text-text-muted leading-relaxed mt-2">
                {t('onboarding.auth.retentionNotice', 'Data retention and deletion timelines are set by this instance administrator. Contact them for access, correction, or deletion requests.')}
              </p>
              <p className="text-xs text-text-muted leading-relaxed mt-2">
                {t('onboarding.auth.noWarrantyNotice')}
              </p>
            </div>
          </form>
        </>
      )}
    </OnboardingCard>
  )
}
