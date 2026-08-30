import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
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

/**
 * Keys used in code but absent from en.json.
 *
 * `t('some.key', 'English default')` renders the default when the key is
 * missing, so an orphan key shows English in *every* locale. Locale parity
 * cannot see this: the key is absent from en.json too, so es-vs-en reports no
 * discrepancy and the gate stays green while the UI stays English.
 *
 * That is exactly how "Search resources" on the Resource Directory shipped
 * untranslated in all 31 locales.
 */
describe('translation keys used in code exist in English', () => {
  // Vitest runs from the frontend package root.
  const SRC = join(process.cwd(), 'src');

  function sourceFiles(dir: string, out: string[] = []): string[] {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        sourceFiles(full, out);
      } else if (/\.tsx?$/.test(entry.name) && !/\.(test|spec)\./.test(entry.name)) {
        out.push(full);
      }
    }
    return out;
  }

  function lookup(key: string): unknown {
    return key
      .split('.')
      .reduce<unknown>(
        (node, part) =>
          node && typeof node === 'object'
            ? (node as Record<string, unknown>)[part]
            : undefined,
        en as unknown
      );
  }

  // A count-based call resolves through i18next's plural suffixes, so the bare
  // key is legitimately absent when `<key>_one` / `<key>_other` are defined.
  function resolves(key: string): boolean {
    if (lookup(key) !== undefined) return true;
    return PLURAL_SUFFIXES.some(
      (suffix) => lookup(`${key}_${suffix}`) !== undefined
    );
  }

  const PLURAL_SUFFIXES = ['one', 'other', 'zero', 'two', 'few', 'many'];

  // Only static single-quoted/double-quoted keys. Template literals and
  // variables are dynamic and cannot be checked here.
  const CALL = /\bt\(\s*['"]([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)['"]/g;

  it('has no translation key that is missing from en.json', () => {
    const orphans = new Set<string>();
    for (const file of sourceFiles(SRC)) {
      const source = readFileSync(file, 'utf8');
      for (const match of source.matchAll(CALL)) {
        if (!resolves(match[1])) {
          orphans.add(`${match[1]} — ${file.slice(SRC.length + 1)}`);
        }
      }
    }
    expect([...orphans].sort()).toEqual([]);
  });
});

/**
 * Dynamic keys: `t(`ns.${value}`)`.
 *
 * The static scan above cannot see these, and a missing entry silently falls
 * back to the English default in every locale — which is how the Admin Guides
 * safety list shipped untranslated. Each dynamic family is registered here with
 * the value set it is built from, so a new value or a renamed key fails loudly.
 *
 * Registering a family is required when adding a new `t(`...${...}`)` call.
 */
describe('dynamic translation key families resolve in English', () => {
  function look(key: string): unknown {
    return key
      .split('.')
      .reduce<unknown>(
        (node, part) =>
          node && typeof node === 'object'
            ? (node as Record<string, unknown>)[part]
            : undefined,
        en as unknown
      );
  }

  const FIELD_TYPES = [
    'text',
    'email',
    'number',
    'textarea',
    'select',
    'checkbox',
    'date',
    'url',
  ];
  const REACHOUT_MODES = ['feedback', 'help', 'support'];
  const QUICK_STEP_COUNT = 5; // AdminGuides.tsx quickSteps
  const SAFETY_ITEM_COUNT = 5; // AdminGuides.tsx safetyBasics

  const families: Array<[string, string[]]> = [
    [
      'admin.fieldTypes',
      FIELD_TYPES.flatMap((type) => [
        `admin.fieldTypes.${type}`,
        `admin.fieldTypes.${type}Desc`,
      ]),
    ],
    [
      'reachout.mode',
      REACHOUT_MODES.map((mode) => `reachout.mode.${mode}.title`),
    ],
    [
      'adminGuides.quickSteps',
      Array.from({ length: QUICK_STEP_COUNT }).flatMap((_, index) => [
        `adminGuides.quickSteps.${index}.title`,
        `adminGuides.quickSteps.${index}.body`,
      ]),
    ],
    [
      'adminGuides.safety.directItems',
      Array.from(
        { length: SAFETY_ITEM_COUNT },
        (_, index) => `adminGuides.safety.directItems.${index}`
      ),
    ],
  ];

  for (const [family, keys] of families) {
    it(`${family} resolves for every value it is built from`, () => {
      expect(keys.filter((key) => look(key) === undefined)).toEqual([]);
    });
  }
});
