import { describe, expect, it } from 'vitest';
import { dynamicTranslationFamilies } from './dynamicTranslationFamilies';
import { localeResources } from './localeCatalog';
import { lookupLocaleMessage } from './localizationContract';

const sageWebRuntimeSources = import.meta.glob(
  '../../../runtime/sage/crates/sage-core/src/web_runtime.rs',
  { eager: true, import: 'default', query: '?raw' }
) as Record<string, string>;

function sageAuthoredActivityKeys(): string[] {
  const source = Object.values(sageWebRuntimeSources)[0] ?? '';
  return [
    ...new Set(
      [...source.matchAll(/['"](chat\.activity(?:\.[A-Za-z0-9_]+)+)['"]/g)].map(
        ([, key]) => key
      )
    ),
  ].sort();
}

describe('Sage Activity structural coverage', () => {
  it('keeps every static Sage Activity key registered and translated for priority locales', () => {
    const sageKeys = sageAuthoredActivityKeys();
    const registeredKeys = new Set(
      dynamicTranslationFamilies.flatMap((family) => family.keys)
    );
    const priorityLocaleCodes = [
      'en',
      'es',
      'fr',
      'ru',
      'ar',
      'zh-Hans',
    ] as const;

    expect(sageKeys.length).toBeGreaterThan(0);
    expect(sageKeys.filter((key) => !registeredKeys.has(key))).toEqual([]);
    for (const code of priorityLocaleCodes) {
      expect(
        sageKeys.filter(
          (key) =>
            lookupLocaleMessage(localeResources[code].translation, key) ===
            undefined
        ),
        code
      ).toEqual([]);
    }
  });
});
