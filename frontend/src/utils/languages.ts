export interface Language {
  code: string;
  nativeName: string;
  englishName: string;
  flag: string;
}

// Order is intentional and drives the language-picker display order (the picker
// renders this array as-is). It is a product/mission call, NOT alphabetical —
// please do not "tidy" it. Languages most likely to be needed by at-risk users
// lead; languages spoken predominantly in stable, low-risk regions are demoted
// to the bottom. See issue #496.
export const LANGUAGES: Language[] = [
  // Priority set — highest likely need for at-risk users.
  { code: 'es', nativeName: 'Español', englishName: 'Spanish', flag: '🇪🇸' },
  { code: 'en', nativeName: 'English', englishName: 'English', flag: '🇺🇸' },
  { code: 'fr', nativeName: 'Français', englishName: 'French', flag: '🇫🇷' },
  { code: 'ru', nativeName: 'Русский', englishName: 'Russian', flag: '🇷🇺' },
  { code: 'ar', nativeName: 'العربية', englishName: 'Arabic', flag: '🇸🇦' },
  {
    code: 'zh-Hans',
    nativeName: '简体中文',
    englishName: 'Chinese (Simplified)',
    flag: '🇨🇳',
  },

  // High-need — large populations facing serious human-rights / authoritarian pressure.
  { code: 'fa', nativeName: 'فارسی', englishName: 'Persian', flag: '🇮🇷' },
  {
    code: 'zh-Hant',
    nativeName: '繁體中文',
    englishName: 'Chinese (Traditional)',
    flag: '🇹🇼',
  },
  {
    code: 'uk',
    nativeName: 'Українська',
    englishName: 'Ukrainian',
    flag: '🇺🇦',
  },
  { code: 'tr', nativeName: 'Türkçe', englishName: 'Turkish', flag: '🇹🇷' },
  { code: 'hi', nativeName: 'हिन्दी', englishName: 'Hindi', flag: '🇮🇳' },
  { code: 'bn', nativeName: 'বাংলা', englishName: 'Bengali', flag: '🇧🇩' },
  {
    code: 'id',
    nativeName: 'Bahasa Indonesia',
    englishName: 'Indonesian',
    flag: '🇮🇩',
  },
  {
    code: 'vi',
    nativeName: 'Tiếng Việt',
    englishName: 'Vietnamese',
    flag: '🇻🇳',
  },
  { code: 'th', nativeName: 'ไทย', englishName: 'Thai', flag: '🇹🇭' },
  { code: 'he', nativeName: 'עברית', englishName: 'Hebrew', flag: '🇮🇱' },
  { code: 'ko', nativeName: '한국어', englishName: 'Korean', flag: '🇰🇷' },
  {
    code: 'pt',
    nativeName: 'Português',
    englishName: 'Portuguese',
    flag: '🇧🇷',
  },
  { code: 'ja', nativeName: '日本語', englishName: 'Japanese', flag: '🇯🇵' },

  // Lower-priority — spoken predominantly in stable, low-risk regions. Demoted.
  { code: 'pl', nativeName: 'Polski', englishName: 'Polish', flag: '🇵🇱' },
  { code: 'de', nativeName: 'Deutsch', englishName: 'German', flag: '🇩🇪' },
  { code: 'it', nativeName: 'Italiano', englishName: 'Italian', flag: '🇮🇹' },
  { code: 'nl', nativeName: 'Nederlands', englishName: 'Dutch', flag: '🇳🇱' },
  { code: 'cs', nativeName: 'Čeština', englishName: 'Czech', flag: '🇨🇿' },
  { code: 'ro', nativeName: 'Română', englishName: 'Romanian', flag: '🇷🇴' },
  { code: 'hu', nativeName: 'Magyar', englishName: 'Hungarian', flag: '🇭🇺' },
  { code: 'el', nativeName: 'Ελληνικά', englishName: 'Greek', flag: '🇬🇷' },
  { code: 'sv', nativeName: 'Svenska', englishName: 'Swedish', flag: '🇸🇪' },
  { code: 'no', nativeName: 'Norsk', englishName: 'Norwegian', flag: '🇳🇴' },
  { code: 'da', nativeName: 'Dansk', englishName: 'Danish', flag: '🇩🇰' },
  { code: 'fi', nativeName: 'Suomi', englishName: 'Finnish', flag: '🇫🇮' },
];

export const STORAGE_KEY_LANGUAGE = 'enclave_language';

// Marks that the user explicitly picked a language (via the switcher), as
// opposed to a value auto-detected/cached by i18next. The instance default
// language must not override an explicit user choice — see InstanceConfigContext.
export const STORAGE_KEY_LANGUAGE_EXPLICIT = 'enclave_language_explicit';

export function markLanguageChosen(): void {
  try {
    localStorage.setItem(STORAGE_KEY_LANGUAGE_EXPLICIT, '1');
  } catch {
    // localStorage may be unavailable (private mode / SSR) — non-fatal.
  }
}

export function hasChosenLanguage(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY_LANGUAGE_EXPLICIT) === '1';
  } catch {
    return false;
  }
}
