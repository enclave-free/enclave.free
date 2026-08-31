export interface Language {
  code: string;
  nativeName: string;
  englishName: string;
  flag: string;
}

import {
  advertisedLocaleCodes,
  advertisedLocales,
  type AdvertisedLocaleCode,
} from '../i18n/localeCatalog';

// Order is intentional and drives the language-picker display order (the picker
// renders this array as-is). It is a product/mission call, NOT alphabetical —
// please do not "tidy" it. Languages most likely to be needed by at-risk users
// lead; languages spoken predominantly in stable, low-risk regions are demoted
// to the bottom. See issue #496.
export const LANGUAGES: Language[] = advertisedLocales.map(
  ({ code, nativeName, englishName, flag }) => ({
    code,
    nativeName,
    englishName,
    flag,
  })
);

export const STORAGE_KEY_LANGUAGE = 'enclave_language';

// Marks that the user explicitly picked a language (via the switcher), as
// opposed to a value auto-detected/cached by i18next. The instance default
// language must not override an explicit user choice — see InstanceConfigContext.
export const STORAGE_KEY_LANGUAGE_EXPLICIT = 'enclave_language_explicit';

export function saveExplicitLanguageChoice(code: string): void {
  try {
    localStorage.setItem(STORAGE_KEY_LANGUAGE, code);
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

/**
 * Return the explicitly selected advertised locale for request propagation.
 *
 * i18next may be using a browser-detected language when a User has not made an
 * explicit choice. Requests must not turn that ambient browser state into a
 * server-side locale preference, so an absent or invalid stored value is
 * represented as undefined and left for the Enclave Control Plane's English
 * fallback.
 */
export function getExplicitLanguageChoice(): AdvertisedLocaleCode | undefined {
  try {
    // Read the marker directly so request provenance stays tied to an actual
    // explicit selection, independently of ambient language detection.
    if (localStorage.getItem(STORAGE_KEY_LANGUAGE_EXPLICIT) !== '1') {
      return undefined;
    }

    const storedLanguage = localStorage.getItem(STORAGE_KEY_LANGUAGE);
    if (storedLanguage === null) {
      return undefined;
    }

    return advertisedLocaleCodes.includes(
      storedLanguage as AdvertisedLocaleCode
    )
      ? (storedLanguage as AdvertisedLocaleCode)
      : undefined;
  } catch {
    return undefined;
  }
}
