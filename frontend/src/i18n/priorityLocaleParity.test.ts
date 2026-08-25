import { describe, expect, it } from 'vitest';
import ar from './locales/ar.json';
import en from './locales/en.json';
import es from './locales/es.json';
import fr from './locales/fr.json';
import ru from './locales/ru.json';
import zhHans from './locales/zh-Hans.json';

type LocaleValue = string | number | boolean | null | LocaleObject;
type LocaleObject = { [key: string]: LocaleValue };

const priorityLocales = { es, fr, ru, ar, 'zh-Hans': zhHans };

const rosterExportKeys = [
  'admin.userRosterExport.decryptUnavailable',
  'admin.userRosterExport.decryptFailed',
  'admin.userRosterExport.prepared',
  'admin.userRosterExport.prepareRequired',
  'admin.userRosterExport.prepareButton',
  'admin.userRosterExport.downloadButton',
  'adminUserManager.prepareVisible',
  'adminUserManager.downloadPrepared',
  'adminUserManager.exportPrepared',
  'adminUserManager.errors.decryptUnavailable',
  'adminUserManager.errors.decryptRoster',
  'adminUserManager.errors.prepareRequired',
];

function flatten(
  value: LocaleObject,
  prefix = '',
  output: Record<string, LocaleValue> = {}
): Record<string, LocaleValue> {
  for (const [key, child] of Object.entries(value)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === 'object' && !Array.isArray(child)) {
      flatten(child, path, output);
    } else {
      output[path] = child;
    }
  }
  return output;
}

function placeholders(value: LocaleValue): string[] {
  if (typeof value !== 'string') return [];
  return [...value.matchAll(/{{\s*([^},\s]+)[^}]*}}/g)]
    .map((match) => match[1])
    .sort();
}

describe('priority locale parity', () => {
  const english = flatten(en as LocaleObject);

  it('localizes the roster preparation flow in every priority locale', () => {
    for (const [locale, messages] of Object.entries({
      en,
      ...priorityLocales,
    })) {
      const translated = flatten(messages as LocaleObject);
      const missing = rosterExportKeys.filter((key) => !(key in translated));
      expect(missing, locale).toEqual([]);
    }
  });

  for (const [locale, messages] of Object.entries(priorityLocales)) {
    const translated = flatten(messages as LocaleObject);

    it(`${locale} contains every English translation key`, () => {
      const missing = Object.keys(english).filter(
        (key) => !(key in translated)
      );
      expect(missing).toEqual([]);
    });

    it(`${locale} preserves interpolation placeholders`, () => {
      const mismatches = Object.entries(english)
        .filter(([key]) => key in translated)
        .filter(
          ([key, value]) =>
            placeholders(value).join(',') !==
            placeholders(translated[key]).join(',')
        )
        .map(([key]) => key);
      expect(mismatches).toEqual([]);
    });

    it(`${locale} contains every plural form its locale can resolve`, () => {
      const pluralBases = Object.keys(english)
        .filter((key) => key.endsWith('_one'))
        .map((key) => key.slice(0, -'_one'.length));
      const categories = new Intl.PluralRules(locale).resolvedOptions()
        .pluralCategories;
      const missing = pluralBases.flatMap((base) =>
        categories
          .map((category) => `${base}_${category}`)
          .filter((key) => !(key in translated))
      );
      expect(missing).toEqual([]);
    });
  }
});
