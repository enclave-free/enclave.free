import { describe, expect, it } from 'vitest';
import {
  advertisedLocales,
  localeResources,
  type AdvertisedLocaleCode,
} from './localeCatalog';
import { dynamicTranslationFamilies } from './dynamicTranslationFamilies';
import {
  inspectDynamicTranslationRegistration,
  inspectLocaleRegistration,
  inspectLocaleStructuralCompleteness,
  inspectStaticCopy,
  lookupLocaleMessage,
} from './localizationContract';
import { staticCopyExemptions } from './staticCopyExemptions';

const productionSources = import.meta.glob('../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

const sourceEntries = Object.entries(productionSources).filter(
  ([file]) => !/\.(test|spec)\./.test(file)
);

const knownMissingDynamicEnglishKeys: string[] = [];

describe('localization contract validator', () => {
  it('reports visible JSX text and user-facing attributes that bypass i18n', () => {
    const report = inspectStaticCopy({
      'components/shared/Example.tsx': `
        export function Example() {
          return <section aria-label="Settings"><h1>Welcome back</h1><input placeholder="Search" title="Search items" alt="A logo" /></section>;
        }
      `,
    });

    expect(report).toEqual([
      {
        file: 'components/shared/Example.tsx',
        kind: 'alt',
        text: 'A logo',
      },
      {
        file: 'components/shared/Example.tsx',
        kind: 'aria-label',
        text: 'Settings',
      },
      {
        file: 'components/shared/Example.tsx',
        kind: 'placeholder',
        text: 'Search',
      },
      {
        file: 'components/shared/Example.tsx',
        kind: 'text',
        text: 'Welcome back',
      },
      {
        file: 'components/shared/Example.tsx',
        kind: 'title',
        text: 'Search items',
      },
    ]);
  });

  it('permits only explicit technical literals and the developer-only dashboard surface', () => {
    const report = inspectStaticCopy(
      {
        'pages/TestDashboard.tsx':
          '<div>Developer diagnostics</div><input aria-label="SQL query" />',
        'components/shared/Example.tsx':
          '<div>Developer diagnostics</div><input aria-label="SQL query" />',
      },
      [
        {
          file: 'pages/TestDashboard.tsx',
          kind: 'text',
          text: 'Developer diagnostics',
          reason: 'developer-only diagnostics surface',
        },
        {
          file: 'pages/TestDashboard.tsx',
          kind: 'aria-label',
          text: 'SQL query',
          reason: 'technical developer control',
        },
        {
          file: 'components/shared/Example.tsx',
          kind: 'aria-label',
          text: 'SQL query',
          reason: 'technical developer control',
        },
      ]
    );

    expect(report).toEqual([
      {
        file: 'components/shared/Example.tsx',
        kind: 'text',
        text: 'Developer diagnostics',
      },
    ]);
  });

  it('reports an Advertised Locale whose resource is omitted', () => {
    const report = inspectLocaleRegistration(['en', 'es'], {
      en: { translation: {} },
    });

    expect(report).toEqual({
      missingResources: ['es'],
      unexpectedResources: [],
    });
  });

  it('finds static copy in JSX expressions, rendered state, display objects, and component props', () => {
    const report = inspectStaticCopy({
      'components/shared/FlowFixture.tsx': `
        function FlowFixture({ tool, busy }: Props) {
          const [error, setError] = useState<string | null>(null);
          const copy = { message: 'Object message', summary: 'Object summary' };
          setError(error ? 'Recovered' : 'Failed to load');
          return <>
            {\`${'${tool.name}'} optional details\`}
            {busy ? 'Loading now' : 'Ready now'}
            {error && <p>{error}</p>}
            {copy.message} {copy.summary}
            <Status label="Visible label" description="Visible description" />
          </>;
        }
      `,
    });

    expect(report).toEqual([
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'description',
        text: 'Visible description',
      },
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'label',
        text: 'Visible label',
      },
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'text',
        text: 'Failed to load',
      },
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'text',
        text: 'Loading now',
      },
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'text',
        text: 'Object message',
      },
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'text',
        text: 'Object summary',
      },
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'text',
        text: 'optional details',
      },
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'text',
        text: 'Ready now',
      },
      {
        file: 'components/shared/FlowFixture.tsx',
        kind: 'text',
        text: 'Recovered',
      },
    ]);
  });

  it('does not treat non-rendered technical bindings as user-facing copy', () => {
    expect(
      inspectStaticCopy({
        'components/shared/TechnicalFixture.tsx': `
          const route = '/admin/database';
          const classes = { message: 'sr-only' };
          function TechnicalFixture() { return <div data-route={route} className={classes.message} />; }
        `,
      })
    ).toEqual([]);
  });

  it('reports static copy stored in a rendered variable', () => {
    expect(
      inspectStaticCopy({
        'components/shared/VariableFixture.tsx': `
          function VariableFixture() {
            const caption = 'Welcome back';
            return <h1>{caption}</h1>;
          }
        `,
      })
    ).toEqual([
      {
        file: 'components/shared/VariableFixture.tsx',
        kind: 'text',
        text: 'Welcome back',
      },
    ]);
  });

  it('preserves the rendered attribute kind and allows translated variables', () => {
    expect(
      inspectStaticCopy({
        'components/shared/VariableAttributeFixture.tsx': `
          function VariableAttributeFixture() {
            const title = 'Open account details';
            const caption = t('account.details');
            return <button title={title}>{caption}</button>;
          }
        `,
      })
    ).toEqual([
      {
        file: 'components/shared/VariableAttributeFixture.tsx',
        kind: 'title',
        text: 'Open account details',
      },
    ]);
  });

  it('does not resolve through parameter or destructuring shadows', () => {
    expect(
      inspectStaticCopy({
        'components/shared/ShadowedVariableFixture.tsx': `
          const caption = 'Wrong outer caption';
          const detail = 'Wrong outer detail';
          function ParameterFixture(caption: string) {
            return <h1>{caption}</h1>;
          }
          function DestructuredFixture({ detail }: Props) {
            return <p>{detail}</p>;
          }
        `,
      })
    ).toEqual([]);
  });

  it('keeps catch and loop bindings inside their lexical scopes', () => {
    expect(
      inspectStaticCopy({
        'components/shared/BlockScopeFixture.tsx': `
          const message = 'Visible after catch';
          const label = 'Visible after loop';
          function BlockScopeFixture(items: string[]) {
            try {
              runTask();
            } catch (message) {
              return <p>{message}</p>;
            }
            for (const label of items) console.log(label);
            return <>{message}{label}</>;
          }
        `,
      })
    ).toEqual([
      {
        file: 'components/shared/BlockScopeFixture.tsx',
        kind: 'text',
        text: 'Visible after catch',
      },
      {
        file: 'components/shared/BlockScopeFixture.tsx',
        kind: 'text',
        text: 'Visible after loop',
      },
    ]);
  });

  it('reports static copy in rendered attribute expressions and state object values', () => {
    const report = inspectStaticCopy({
      'components/shared/AttributeFlowFixture.tsx': `
        function AttributeFlow({ label }: Props) {
          const [result, setResult] = useState<Result | null>(null);
          return <>
            <button aria-label={\`Open help for \${label}\`} title={ready ? 'Ready help' : 'Open help'} />
            {result && <output>{result.items[0].message}</output>}
            <button onClick={() => setResult({ items: [{ message: 'Query execution failed' }] })}>Run</button>
          </>;
        }
      `,
    });

    expect(report).toEqual([
      {
        file: 'components/shared/AttributeFlowFixture.tsx',
        kind: 'aria-label',
        text: 'Open help for',
      },
      {
        file: 'components/shared/AttributeFlowFixture.tsx',
        kind: 'text',
        text: 'Query execution failed',
      },
      {
        file: 'components/shared/AttributeFlowFixture.tsx',
        kind: 'text',
        text: 'Run',
      },
      {
        file: 'components/shared/AttributeFlowFixture.tsx',
        kind: 'title',
        text: 'Open help',
      },
      {
        file: 'components/shared/AttributeFlowFixture.tsx',
        kind: 'title',
        text: 'Ready help',
      },
    ]);
  });

  it('recognizes localized t fallbacks and does not flag their English defaults', () => {
    expect(
      inspectStaticCopy({
        'components/shared/LocalizedFixture.tsx': `
          function LocalizedFixture() {
            return <button aria-label={t('common.help', 'Open help')}>{t('common.run', 'Run')}</button>;
          }
        `,
      })
    ).toEqual([]);
  });

  it('reports an English key missing from a locale', () => {
    const report = inspectLocaleStructuralCompleteness(
      { common: { save: 'Save', cancel: 'Cancel' } },
      { common: { save: 'Guardar' } },
      'es'
    );

    expect(report.missingKeys).toEqual(['common.cancel']);
  });

  it('reports interpolation placeholders that a locale does not preserve', () => {
    const report = inspectLocaleStructuralCompleteness(
      { greeting: 'Hello, {{name}}. Step {{current}} of {{total}}.' },
      { greeting: 'Hola, {{name}}. Paso {{current}}.' },
      'es'
    );

    expect(report.placeholderMismatches).toEqual(['greeting']);
  });

  it('reports plural categories required by the locale', () => {
    const report = inspectLocaleStructuralCompleteness(
      {
        attempts_one: '{{count}} attempt',
        attempts_other: '{{count}} attempts',
      },
      {
        attempts_one: '{{count}} محاولة',
        attempts_other: '{{count}} محاولة',
      },
      'ar'
    );

    expect(report.missingPluralForms).toEqual([
      'attempts_few',
      'attempts_many',
      'attempts_two',
      'attempts_zero',
    ]);
  });

  it('reports an unregistered dynamic translation-key family', () => {
    const report = inspectDynamicTranslationRegistration(
      {
        'Example.tsx':
          'const { t } = useTranslation(); t(`example.${status}.label`)',
      },
      []
    );

    expect(report.unregisteredTemplates).toEqual([
      'example.${}.label — Example.tsx',
    ]);
    expect(report.unsupportedDynamicCalls).toEqual([]);
  });

  it('reports an aliased translation call with an unregistered family', () => {
    const report = inspectDynamicTranslationRegistration(
      {
        'Aliased.tsx':
          'const { t: translate } = useTranslation(); translate(`aliased.${status}.label`)',
      },
      []
    );

    expect(report.unregisteredTemplates).toEqual([
      'aliased.${}.label — Aliased.tsx',
    ]);
    expect(report.unsupportedDynamicCalls).toEqual([]);
  });

  it('reports an optional call with an unregistered family', () => {
    const report = inspectDynamicTranslationRegistration(
      {
        'Optional.tsx':
          'const { t: localize } = useTranslation(); localize?.(`optional.${status}.label`)',
      },
      []
    );

    expect(report.unregisteredTemplates).toEqual([
      'optional.${}.label — Optional.tsx',
    ]);
    expect(report.unsupportedDynamicCalls).toEqual([]);
  });

  it('recognizes direct i18n.t calls', () => {
    const report = inspectDynamicTranslationRegistration(
      { 'Direct.ts': 'i18n.t(`direct.${status}.label`)' },
      []
    );

    expect(report).toEqual({
      unregisteredTemplates: ['direct.${}.label — Direct.ts'],
      unsupportedDynamicCalls: [],
    });
  });

  it('permits inline static literals for identified translation calls', () => {
    const report = inspectDynamicTranslationRegistration(
      {
        'Static.tsx':
          "const { t: translate } = useTranslation(); translate('common.save'); i18n.t?.(`common.cancel`)",
      },
      []
    );

    expect(report).toEqual({
      unregisteredTemplates: [],
      unsupportedDynamicCalls: [],
    });
  });

  it('reports a translation key stored in a variable as unsupported', () => {
    const report = inspectDynamicTranslationRegistration(
      {
        'Variable.tsx':
          'const { t } = useTranslation(); const key = `example.${status}.label`; t(key)',
      },
      []
    );

    expect(report).toEqual({
      unregisteredTemplates: [],
      unsupportedDynamicCalls: ['t(key) — Variable.tsx'],
    });
  });

  it('reports concatenated translation keys as unsupported', () => {
    const report = inspectDynamicTranslationRegistration(
      {
        'Concatenated.tsx':
          "const { t } = useTranslation(); t('example.' + status + '.label')",
      },
      []
    );

    expect(report).toEqual({
      unregisteredTemplates: [],
      unsupportedDynamicCalls: [
        "t('example.' + status + '.label') — Concatenated.tsx",
      ],
    });
  });

  it('reports a wrapper forwarding its key to t as unsupported', () => {
    const report = inspectDynamicTranslationRegistration(
      {
        'Wrapper.tsx':
          'function localize(t: TFunction, key: string) { return t(key); }',
      },
      []
    );

    expect(report).toEqual({
      unregisteredTemplates: [],
      unsupportedDynamicCalls: ['t(key) — Wrapper.tsx'],
    });
  });

  it('ignores unrelated calls with dynamic template arguments', () => {
    const report = inspectDynamicTranslationRegistration(
      { 'Navigation.tsx': 'navigate(`users.${id}.profile`)' },
      []
    );

    expect(report).toEqual({
      unregisteredTemplates: [],
      unsupportedDynamicCalls: [],
    });
  });
});

describe('Advertised Locale structural contract', () => {
  const english = localeResources.en.translation;
  const reports = Object.fromEntries(
    advertisedLocales.map(({ code, translation }) => [
      code,
      inspectLocaleStructuralCompleteness(english, translation, code),
    ])
  ) as Record<
    AdvertisedLocaleCode,
    ReturnType<typeof inspectLocaleStructuralCompleteness>
  >;

  it('checks registration from the complete Advertised Locale catalog', () => {
    expect(
      inspectLocaleRegistration(
        advertisedLocales.map(({ code }) => code),
        localeResources
      )
    ).toEqual({ missingResources: [], unexpectedResources: [] });
  });

  it('keeps every existing translation placeholder-compatible with English', () => {
    for (const { code } of advertisedLocales) {
      expect(reports[code].placeholderMismatches, code).toEqual([]);
    }
  });

  it('has no missing keys or locale-specific plural forms', () => {
    for (const { code } of advertisedLocales) {
      expect(reports[code].missingKeys, code).toEqual([]);
      expect(reports[code].missingPluralForms, code).toEqual([]);
    }
  });
});

describe('translation keys used by frontend source', () => {
  const english = localeResources.en.translation;
  const pluralSuffixes = ['one', 'other', 'zero', 'two', 'few', 'many'];
  const staticCall = /\bt\(\s*['"]([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)['"]/g;

  const resolvesEnglishKey = (key: string) =>
    lookupLocaleMessage(english, key) !== undefined ||
    pluralSuffixes.some(
      (suffix) => lookupLocaleMessage(english, `${key}_${suffix}`) !== undefined
    );

  it('has no static translation key missing from English', () => {
    const missing = new Set<string>();
    for (const [file, source] of sourceEntries) {
      for (const match of source.matchAll(staticCall)) {
        if (!resolvesEnglishKey(match[1])) {
          missing.add(`${match[1]} — ${file.replace('../', '')}`);
        }
      }
    }
    expect([...missing].sort()).toEqual([]);
  });

  it('requires every dynamic translation-key call to register its family', () => {
    expect(
      inspectDynamicTranslationRegistration(
        Object.fromEntries(sourceEntries),
        dynamicTranslationFamilies
      )
    ).toEqual({
      unregisteredTemplates: [],
      unsupportedDynamicCalls: [],
    });
  });

  it('resolves every allowed dynamic key or exposes the exact #661 debt', () => {
    const missing = dynamicTranslationFamilies.flatMap((family) =>
      family.keys
        .filter((key) => !resolvesEnglishKey(key))
        .map((key) => `${family.name}: ${key}`)
    );

    expect(missing.sort()).toEqual([...knownMissingDynamicEnglishKeys].sort());
  });

  it('keeps every non-test frontend product source free of raw static copy', () => {
    expect(
      inspectStaticCopy(Object.fromEntries(sourceEntries), staticCopyExemptions)
    ).toEqual([]);
  });
});
