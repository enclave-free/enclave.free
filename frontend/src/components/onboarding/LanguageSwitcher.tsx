import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, ChevronDown, Globe } from 'lucide-react'
import { LANGUAGES, STORAGE_KEY_LANGUAGE } from '../../utils/languages'

function getCurrentLanguage(language: string) {
  return (
    LANGUAGES.find((lang) => lang.code === language) ??
    LANGUAGES.find((lang) => language.startsWith(`${lang.code}-`)) ??
    LANGUAGES[0]
  )
}

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const currentLang = getCurrentLanguage(i18n.language)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }

    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  const handleLanguageChange = (code: string) => {
    localStorage.setItem(STORAGE_KEY_LANGUAGE, code)
    void i18n.changeLanguage(code)
    setOpen(false)
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="btn-ghost flex min-h-10 items-center gap-1.5 rounded-lg px-3 py-2 text-xs text-text-muted transition-colors hover:text-text"
        aria-label={t('adminOnboarding.extracted.change_language_789b14', 'Change language')}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <Globe className="h-3.5 w-3.5" aria-hidden="true" />
        <span>{currentLang.nativeName}</span>
        <ChevronDown
          className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-1 max-h-64 w-52 overflow-y-auto rounded-xl border border-border bg-surface-raised shadow-lg animate-fade-in-scale"
        >
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              type="button"
              role="menuitemradio"
              aria-checked={lang.code === currentLang.code}
              onClick={() => handleLanguageChange(lang.code)}
              className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
                lang.code === currentLang.code
                  ? 'bg-accent/5 text-accent'
                  : 'text-text-secondary hover:bg-surface-overlay hover:text-text'
              }`}
            >
              <span className="text-base leading-none" aria-hidden="true">
                {lang.flag}
              </span>
              <span>{lang.nativeName}</span>
              {lang.code === currentLang.code && (
                <Check className="ml-auto h-3.5 w-3.5 shrink-0 text-accent" aria-hidden="true" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
