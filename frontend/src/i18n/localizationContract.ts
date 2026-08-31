import type { LocaleMessages } from './localeCatalog';
import * as ts from 'typescript';

type LocaleValue = unknown;

export interface LocaleRegistrationReport {
  missingResources: string[];
  unexpectedResources: string[];
}

export interface LocaleStructuralCompletenessReport {
  missingKeys: string[];
  placeholderMismatches: string[];
  missingPluralForms: string[];
}

export interface DynamicTranslationFamily {
  name: string;
  template: string;
  keys: readonly string[];
}

export interface DynamicTranslationRegistrationReport {
  unregisteredTemplates: string[];
  unsupportedDynamicCalls: string[];
}

export type StaticCopyKind =
  | 'text'
  | 'placeholder'
  | 'title'
  | 'aria-label'
  | 'alt'
  | 'label'
  | 'message'
  | 'description'
  | 'summary'
  | 'emptyText'
  | 'errorText';

export interface StaticCopyExemption {
  file: string;
  kind: StaticCopyKind;
  text: string;
  reason: string;
}

export interface StaticCopyViolation {
  file: string;
  kind: StaticCopyKind;
  text: string;
}

const translatableAttributes = new Set<StaticCopyKind>([
  'placeholder',
  'title',
  'aria-label',
  'alt',
  'label',
  'message',
  'description',
  'summary',
  'emptyText',
  'errorText',
]);

const technicalAttributes = new Set(['aria-controls', 'aria-labelledby']);
const displayPropertyNames = new Set([
  'label',
  'title',
  'description',
  'summary',
  'message',
  'empty',
  'error',
]);

function normalizedStaticText(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

function isLikelyUserFacingText(text: string): boolean {
  return /\p{L}/u.test(text) && !/^[{}$()[\]<>/\\|=;:_.,\-+*#]+$/.test(text);
}

function staticCopyExempt(
  violation: StaticCopyViolation,
  exemptions: readonly StaticCopyExemption[]
): boolean {
  return exemptions.some(
    (exemption) =>
      exemption.file === violation.file &&
      exemption.kind === violation.kind &&
      exemption.text === violation.text
  );
}

/**
 * Finds literal product copy in TSX without attempting to infer language from
 * the literal itself. Callers must explicitly exempt technical/developer-only
 * strings, keeping the exception reviewable and scoped to one file/value.
 */
export function inspectStaticCopy(
  sources: Record<string, string>,
  exemptions: readonly StaticCopyExemption[] = []
): StaticCopyViolation[] {
  const violations: StaticCopyViolation[] = [];

  for (const [file, source] of Object.entries(sources)) {
    const sourceFile = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX
    );

    const add = (kind: StaticCopyKind, value: string) => {
      const text = normalizedStaticText(value);
      if (!isLikelyUserFacingText(text)) return;
      const violation = { file, kind, text };
      if (!staticCopyExempt(violation, exemptions)) violations.push(violation);
    };

    const inspectExpression = (
      expression: ts.Expression,
      kind: StaticCopyKind = 'text'
    ): void => {
      if (
        ts.isCallExpression(expression) &&
        ((ts.isIdentifier(expression.expression) &&
          expression.expression.text === 't') ||
          (ts.isPropertyAccessExpression(expression.expression) &&
            expression.expression.name.text === 't'))
      ) {
        return;
      }
      if (ts.isStringLiteralLike(expression)) {
        add(kind, expression.text);
        return;
      }
      if (ts.isTemplateExpression(expression)) {
        add(kind, expression.head.text);
        for (const span of expression.templateSpans) {
          add(kind, span.literal.text);
        }
        return;
      }
      if (ts.isConditionalExpression(expression)) {
        inspectExpression(expression.whenTrue, kind);
        inspectExpression(expression.whenFalse, kind);
        return;
      }
      if (ts.isBinaryExpression(expression)) {
        const operator = expression.operatorToken.kind;
        if (
          operator === ts.SyntaxKind.AmpersandAmpersandToken ||
          operator === ts.SyntaxKind.BarBarToken ||
          operator === ts.SyntaxKind.QuestionQuestionToken ||
          operator === ts.SyntaxKind.PlusToken
        ) {
          inspectExpression(expression.left, kind);
          inspectExpression(expression.right, kind);
        }
        return;
      }
      if (ts.isObjectLiteralExpression(expression)) {
        for (const property of expression.properties) {
          if (!ts.isPropertyAssignment(property)) continue;
          const name = property.name;
          const propertyName =
            ts.isIdentifier(name) || ts.isStringLiteral(name)
              ? name.text
              : undefined;
          if (propertyName && displayPropertyNames.has(propertyName)) {
            inspectExpression(property.initializer, kind);
          } else if (
            ts.isObjectLiteralExpression(property.initializer) ||
            ts.isArrayLiteralExpression(property.initializer)
          ) {
            inspectExpression(property.initializer, kind);
          }
        }
        return;
      }
      if (ts.isArrayLiteralExpression(expression)) {
        for (const element of expression.elements) {
          if (ts.isExpression(element)) inspectExpression(element, kind);
        }
        return;
      }
      if (
        ts.isParenthesizedExpression(expression) ||
        ts.isAsExpression(expression) ||
        ts.isNonNullExpression(expression) ||
        ts.isTypeAssertionExpression(expression)
      ) {
        inspectExpression(expression.expression, kind);
      }
    };

    const stateBindings = new Map<
      string,
      { setter: string; initialValue?: ts.Expression }
    >();
    const objectBindings = new Map<string, Map<string, ts.Expression>>();
    const renderedStateNames = new Set<string>();
    const renderedObjectProperties = new Set<string>();

    const collectRenderedBindings = (node: ts.Node, rendered = false): void => {
      let isRendered = rendered;
      if (ts.isJsxExpression(node)) {
        const parent = node.parent;
        if (ts.isJsxAttribute(parent)) {
          const name = ts.isIdentifier(parent.name)
            ? parent.name.text
            : undefined;
          isRendered = Boolean(
            name && translatableAttributes.has(name as StaticCopyKind)
          );
        } else {
          isRendered = true;
        }
      }
      if (
        isRendered &&
        ts.isBinaryExpression(node) &&
        [
          ts.SyntaxKind.EqualsEqualsToken,
          ts.SyntaxKind.EqualsEqualsEqualsToken,
          ts.SyntaxKind.ExclamationEqualsToken,
          ts.SyntaxKind.ExclamationEqualsEqualsToken,
          ts.SyntaxKind.LessThanToken,
          ts.SyntaxKind.LessThanEqualsToken,
          ts.SyntaxKind.GreaterThanToken,
          ts.SyntaxKind.GreaterThanEqualsToken,
        ].includes(node.operatorToken.kind)
      ) {
        return;
      }
      if (isRendered && ts.isIdentifier(node) && stateBindings.has(node.text)) {
        renderedStateNames.add(node.text);
      }
      if (isRendered && ts.isPropertyAccessExpression(node)) {
        const object = node.expression;
        const property = node.name.text;
        if (
          ts.isIdentifier(object) &&
          objectBindings.get(object.text)?.has(property)
        ) {
          renderedObjectProperties.add(`${object.text}.${property}`);
        }
      }
      ts.forEachChild(node, (child) =>
        collectRenderedBindings(child, isRendered)
      );
    };

    const collectBindings = (node: ts.Node): void => {
      if (
        ts.isVariableDeclaration(node) &&
        ts.isArrayBindingPattern(node.name) &&
        node.name.elements.length >= 2 &&
        node.initializer &&
        ts.isCallExpression(node.initializer) &&
        ts.isIdentifier(node.initializer.expression) &&
        node.initializer.expression.text === 'useState'
      ) {
        const state = node.name.elements[0];
        const setter = node.name.elements[1];
        if (
          ts.isBindingElement(state) &&
          ts.isIdentifier(state.name) &&
          ts.isBindingElement(setter) &&
          ts.isIdentifier(setter.name)
        ) {
          stateBindings.set(state.name.text, {
            setter: setter.name.text,
            initialValue: node.initializer.arguments[0],
          });
        }
      }
      if (
        ts.isVariableDeclaration(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer &&
        ts.isObjectLiteralExpression(node.initializer)
      ) {
        const properties = new Map<string, ts.Expression>();
        for (const property of node.initializer.properties) {
          if (!ts.isPropertyAssignment(property)) continue;
          const name = property.name;
          const propertyName =
            ts.isIdentifier(name) || ts.isStringLiteral(name)
              ? name.text
              : undefined;
          if (propertyName && displayPropertyNames.has(propertyName)) {
            properties.set(propertyName, property.initializer);
          }
        }
        if (properties.size > 0) objectBindings.set(node.name.text, properties);
      }
      ts.forEachChild(node, collectBindings);
    };

    collectBindings(sourceFile);
    collectRenderedBindings(sourceFile);

    const visit = (node: ts.Node): void => {
      if (ts.isJsxText(node)) add('text', node.getText(sourceFile));

      if (ts.isJsxAttribute(node) && node.initializer) {
        const attributeName = ts.isIdentifier(node.name)
          ? node.name.text
          : undefined;
        const kind = attributeName as StaticCopyKind;
        if (translatableAttributes.has(kind)) {
          if (ts.isStringLiteral(node.initializer)) {
            add(kind, node.initializer.text);
          } else if (
            ts.isJsxExpression(node.initializer) &&
            node.initializer.expression
          ) {
            inspectExpression(node.initializer.expression, kind);
          }
        } else if (attributeName && technicalAttributes.has(attributeName)) {
          // IDs are implementation literals, even when they contain words.
        }
      }

      if (ts.isJsxExpression(node) && node.expression) {
        const parent = node.parent;
        if (!ts.isJsxAttribute(parent)) inspectExpression(node.expression);
      }

      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
        const setterName = node.expression.text;
        const state = [...stateBindings.entries()].find(
          ([, binding]) => binding.setter === setterName
        );
        if (state && renderedStateNames.has(state[0])) {
          for (const argument of node.arguments) {
            if (ts.isExpression(argument)) inspectExpression(argument);
          }
        }
      }

      if (ts.isPropertyAccessExpression(node)) {
        const object = node.expression;
        if (ts.isIdentifier(object)) {
          const value = objectBindings.get(object.text)?.get(node.name.text);
          if (
            value &&
            renderedObjectProperties.has(`${object.text}.${node.name.text}`)
          ) {
            inspectExpression(value);
          }
        }
      }

      ts.forEachChild(node, visit);
    };

    visit(sourceFile);
  }

  return violations.sort(
    (left, right) =>
      left.file.localeCompare(right.file) ||
      left.kind.localeCompare(right.kind) ||
      left.text.localeCompare(right.text)
  );
}

export function flattenLocaleMessages(
  value: LocaleMessages,
  prefix = '',
  output: Record<string, LocaleValue> = {}
): Record<string, LocaleValue> {
  for (const [key, child] of Object.entries(value)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === 'object' && !Array.isArray(child)) {
      flattenLocaleMessages(child as LocaleMessages, path, output);
    } else {
      output[path] = child;
    }
  }
  return output;
}

export function lookupLocaleMessage(
  messages: LocaleMessages,
  key: string
): LocaleValue {
  return key.split('.').reduce<LocaleValue>((node, part) => {
    if (!node || typeof node !== 'object' || Array.isArray(node)) {
      return undefined;
    }
    return (node as LocaleMessages)[part];
  }, messages);
}

export function interpolationPlaceholders(value: LocaleValue): string[] {
  if (typeof value !== 'string') return [];
  return [...value.matchAll(/{{\s*([^},\s]+)[^}]*}}/g)]
    .map((match) => match[1])
    .sort();
}

export function inspectLocaleRegistration(
  advertisedCodes: readonly string[],
  resources: Record<string, unknown>
): LocaleRegistrationReport {
  const advertised = new Set(advertisedCodes);
  const registered = Object.keys(resources);

  return {
    missingResources: advertisedCodes
      .filter((code) => !registered.includes(code))
      .sort(),
    unexpectedResources: registered
      .filter((code) => !advertised.has(code))
      .sort(),
  };
}

export function inspectLocaleStructuralCompleteness(
  englishMessages: LocaleMessages,
  localeMessages: LocaleMessages,
  locale: string
): LocaleStructuralCompletenessReport {
  const english = flattenLocaleMessages(englishMessages);
  const translated = flattenLocaleMessages(localeMessages);
  const missingKeys = Object.keys(english)
    .filter((key) => !(key in translated))
    .sort();
  const placeholderMismatches = Object.entries(english)
    .filter(([key]) => key in translated)
    .filter(
      ([key, value]) =>
        interpolationPlaceholders(value).join(',') !==
        interpolationPlaceholders(translated[key]).join(',')
    )
    .map(([key]) => key)
    .sort();

  const pluralBases = Object.keys(english)
    .filter((key) => key.endsWith('_one'))
    .map((key) => key.slice(0, -'_one'.length));
  const pluralCategories = new Intl.PluralRules(locale).resolvedOptions()
    .pluralCategories;
  const missingPluralForms = pluralBases
    .flatMap((base) =>
      pluralCategories
        .map((category) => `${base}_${category}`)
        .filter((key) => !(key in translated))
    )
    .sort();

  return {
    missingKeys,
    placeholderMismatches,
    missingPluralForms,
  };
}

export function normalizeDynamicTranslationTemplate(template: string): string {
  return template.replace(/\$\{[^}]+\}/g, '${}');
}

export function inspectDynamicTranslationRegistration(
  sources: Record<string, string>,
  families: readonly DynamicTranslationFamily[]
): DynamicTranslationRegistrationReport {
  const registered = new Set(
    families.map(({ template }) =>
      normalizeDynamicTranslationTemplate(template)
    )
  );
  const unregisteredTemplates = new Set<string>();
  const unsupportedDynamicCalls = new Set<string>();

  const templateFrom = (node: ts.TemplateExpression): string =>
    node.templateSpans.reduce(
      (template, span) => template + '${}' + span.literal.text,
      node.head.text
    );

  for (const [file, source] of Object.entries(sources)) {
    const sourceFile = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
    );
    const translationBindings = new Set<string>();

    const addIdentifierBinding = (name: ts.BindingName): void => {
      if (ts.isIdentifier(name)) translationBindings.add(name.text);
    };

    const collectTranslationBindings = (node: ts.Node): void => {
      if (
        ts.isVariableDeclaration(node) &&
        ts.isObjectBindingPattern(node.name) &&
        node.initializer &&
        ts.isCallExpression(node.initializer) &&
        ts.isIdentifier(node.initializer.expression) &&
        node.initializer.expression.text === 'useTranslation'
      ) {
        for (const element of node.name.elements) {
          const exportedName = element.propertyName ?? element.name;
          if (ts.isIdentifier(exportedName) && exportedName.text === 't') {
            addIdentifierBinding(element.name);
          }
        }
      }

      if (
        (ts.isParameter(node) || ts.isVariableDeclaration(node)) &&
        node.type?.getText(sourceFile).match(/\bTFunction\b/)
      ) {
        addIdentifierBinding(node.name);
      }

      ts.forEachChild(node, collectTranslationBindings);
    };

    collectTranslationBindings(sourceFile);

    const isTranslationCallee = (
      callee: ts.LeftHandSideExpression
    ): boolean => {
      if (ts.isIdentifier(callee)) {
        return translationBindings.has(callee.text);
      }
      return (
        ts.isPropertyAccessExpression(callee) &&
        callee.name.text === 't' &&
        ts.isIdentifier(callee.expression) &&
        callee.expression.text === 'i18n'
      );
    };

    const visit = (node: ts.Node): void => {
      if (ts.isCallExpression(node) && isTranslationCallee(node.expression)) {
        const firstArgument = node.arguments[0];
        if (firstArgument && ts.isTemplateExpression(firstArgument)) {
          const template = templateFrom(firstArgument);
          if (!registered.has(template)) {
            unregisteredTemplates.add(`${template} — ${file}`);
          }
        } else if (firstArgument && !ts.isStringLiteralLike(firstArgument)) {
          unsupportedDynamicCalls.add(`${node.getText(sourceFile)} — ${file}`);
        }
      }
      ts.forEachChild(node, visit);
    };

    visit(sourceFile);
  }

  return {
    unregisteredTemplates: [...unregisteredTemplates].sort(),
    unsupportedDynamicCalls: [...unsupportedDynamicCalls].sort(),
  };
}
