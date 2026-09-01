import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { localeResources } from './localeCatalog';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: localeResources,
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'enclave_language',
      // Explicit language choices are persisted by the onboarding/switcher
      // helper. Do not cache navigator detection into the same preference key.
      caches: [],
    },
  });

export default i18n;

function updateDocumentLocale(language: string): void {
  if (typeof document !== 'undefined') {
    const resolvedLanguage = i18n.resolvedLanguage ?? language;
    document.documentElement.lang = resolvedLanguage;
    document.documentElement.dir = i18n.dir(resolvedLanguage);
  }
}

i18n.on('languageChanged', updateDocumentLocale);
updateDocumentLocale(i18n.language);
