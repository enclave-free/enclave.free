import { describe, expect, it } from 'vitest';
import controlPlaneModelsSource from '../../../backend/app/models.py?raw';
import {
  advertisedLocaleCodes,
  advertisedLocales,
  localeResources,
} from './localeCatalog';
import { LANGUAGES } from '../utils/languages';

const EXPECTED_MISSION_ORDER = [
  'es',
  'en',
  'fr',
  'ru',
  'ar',
  'zh-Hans',
  'fa',
  'zh-Hant',
  'uk',
  'tr',
  'hi',
  'bn',
  'id',
  'vi',
  'th',
  'he',
  'ko',
  'pt',
  'ja',
  'pl',
  'de',
  'it',
  'nl',
  'cs',
  'ro',
  'hu',
  'el',
  'sv',
  'no',
  'da',
  'fi',
];

function controlPlaneAcceptedLocaleCodes(source: string): string[] {
  const assignment = source.match(
    /SUPPORTED_DEFAULT_LANGUAGES\s*=\s*\{([\s\S]*?)\n\}/
  );
  if (!assignment) return [];
  return [...assignment[1].matchAll(/["']([^"']+)["']/g)]
    .map((match) => match[1])
    .sort();
}

describe('Advertised Locale catalog', () => {
  it('preserves the approved mission-driven order for all 31 locales', () => {
    expect(advertisedLocaleCodes).toEqual(EXPECTED_MISSION_ORDER);
    expect(advertisedLocales).toHaveLength(31);
  });

  it('registers one translation resource for every Advertised Locale', () => {
    expect(Object.keys(localeResources).sort()).toEqual(
      [...advertisedLocaleCodes].sort()
    );
  });

  it('provides onboarding choices from the same catalog metadata', () => {
    expect(LANGUAGES).toEqual(
      advertisedLocales.map(({ code, nativeName, englishName, flag }) => ({
        code,
        nativeName,
        englishName,
        flag,
      }))
    );
  });

  it('matches every locale accepted by the Enclave Control Plane', () => {
    expect([...advertisedLocaleCodes].sort()).toEqual(
      controlPlaneAcceptedLocaleCodes(controlPlaneModelsSource)
    );
  });
});
