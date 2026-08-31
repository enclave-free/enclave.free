import { describe, expect, it, vi } from 'vitest';
import type { TFunction } from 'i18next';
import {
  translateActivityMessage,
  translateActivityValues,
} from './conversationActivityI18n';

describe('conversation activity localization', () => {
  it('translates nested built-in tool descriptors before joining selected tools', () => {
    const t = vi.fn((key: string, options?: Record<string, unknown>) => {
      const translations: Record<string, string> = {
        'chat.activity.tool.curatedResources.title': 'Recursos seleccionados',
      };
      return translations[key] ?? String(options?.defaultValue ?? key);
    }) as unknown as TFunction;

    const values = translateActivityValues(t, {
      selectedTools: [
        {
          id: 'find_resources',
          titleKey: 'chat.activity.tool.curatedResources.title',
        },
        { id: 'provider_custom_tool', displayName: 'Partner Tool' },
      ],
    });

    expect(values).toEqual({
      selectedTools: 'Recursos seleccionados, Partner Tool',
    });
    expect(t).toHaveBeenCalledWith(
      'chat.activity.tool.curatedResources.title',
      expect.objectContaining({ defaultValue: 'find_resources' })
    );
  });

  it('fills toolName from a built-in title descriptor for tool summaries', () => {
    const t = vi.fn((key: string, options?: Record<string, unknown>) => {
      const translations: Record<string, string> = {
        'chat.activity.tool.databaseQuery.title': 'Database Query',
      };
      return translations[key] ?? String(options?.defaultValue ?? key);
    }) as unknown as TFunction;

    expect(
      translateActivityValues(t, {
        toolId: 'db-query',
        titleKey: 'chat.activity.tool.databaseQuery.title',
      })
    ).toEqual({
      toolId: 'db-query',
      titleKey: 'chat.activity.tool.databaseQuery.title',
      toolName: 'Database Query',
    });
  });

  it('uses compatibility English only when a key is absent or unresolved', () => {
    const t = vi.fn((key: string, options?: Record<string, unknown>) =>
      key === 'chat.activity.known'
        ? 'Localized'
        : String(options?.defaultValue ?? key)
    ) as unknown as TFunction;

    expect(
      translateActivityMessage(t, 'chat.activity.known', {}, 'English')
    ).toBe('Localized');
    expect(
      translateActivityMessage(t, 'chat.activity.unknown', {}, 'English')
    ).toBe('English');
    expect(
      translateActivityMessage(t, 'chat.activity.unknown', {}, undefined)
    ).toBeUndefined();
    expect(translateActivityMessage(t, undefined, {}, 'Legacy')).toBe('Legacy');
  });
});
