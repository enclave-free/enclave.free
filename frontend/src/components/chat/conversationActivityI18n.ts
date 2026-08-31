import type { TFunction } from 'i18next';

export type ConversationActivityMessageValues = Record<string, unknown>;

export interface ConversationActivityTitleDescriptor {
  titleKey?: string;
  titleValues?: ConversationActivityMessageValues;
  fallback?: string;
}

export function translateActivityMessage(
  t: TFunction,
  key: string | undefined,
  values: ConversationActivityMessageValues | undefined,
  fallback: string | undefined
): string | undefined {
  if (!key) return fallback;
  const namespace = 'chat.activity.';
  if (!key.startsWith(namespace)) return fallback;
  const translationKey = `chat.activity.${key.slice(namespace.length)}`;
  const translated = t(`chat.activity.${key.slice(namespace.length)}`, {
    ...(values ?? {}),
    ...(fallback !== undefined ? { defaultValue: fallback } : {}),
  });
  if (typeof translated !== 'string' || translated === translationKey) {
    return fallback;
  }
  return translated;
}

export function translateActivityValues(
  t: TFunction,
  values: ConversationActivityMessageValues | undefined,
  titleDescriptor?: ConversationActivityTitleDescriptor
): ConversationActivityMessageValues {
  if (!values) return {};
  const selectedTools = values.selectedTools;
  const changedSettings = values.changedSettings;
  const translatedValues = { ...values };
  const titleKey =
    typeof values.titleKey === 'string'
      ? values.titleKey
      : titleDescriptor?.titleKey;
  const titleValues =
    values.titleValues &&
    typeof values.titleValues === 'object' &&
    !Array.isArray(values.titleValues)
      ? (values.titleValues as ConversationActivityMessageValues)
      : titleDescriptor?.titleValues;
  const titleFallback =
    typeof values.titleFallback === 'string'
      ? values.titleFallback
      : titleDescriptor?.fallback;

  if (typeof values.toolName !== 'string' && titleKey) {
    const localizedToolName = translateActivityMessage(
      t,
      titleKey,
      titleValues,
      titleFallback ??
        (typeof values.toolId === 'string' ? values.toolId : undefined)
    );
    if (localizedToolName) translatedValues.toolName = localizedToolName;
  }

  if (Array.isArray(selectedTools)) {
    translatedValues.selectedTools = selectedTools
      .map((tool) => {
        if (!tool || typeof tool !== 'object') return String(tool ?? '');
        const descriptor = tool as Record<string, unknown>;
        if (typeof descriptor.titleKey === 'string') {
          return translateActivityMessage(
            t,
            descriptor.titleKey,
            undefined,
            typeof descriptor.displayName === 'string'
              ? descriptor.displayName
              : typeof descriptor.id === 'string'
                ? descriptor.id
                : 'Tool'
          );
        }
        if (typeof descriptor.displayName === 'string') {
          return descriptor.displayName;
        }
        return typeof descriptor.id === 'string' ? descriptor.id : 'Tool';
      })
      .join(', ');
  }

  if (Array.isArray(changedSettings)) {
    translatedValues.changedSettings = changedSettings
      .filter((setting): setting is string => typeof setting === 'string')
      .join(', ');
  }

  return translatedValues;
}
