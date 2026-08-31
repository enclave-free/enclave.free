import { describe, expect, it } from 'vitest';
import i18n from './index';
import { localeResources } from './localeCatalog';
import { deploymentReadinessStatuses } from './dynamicTranslationFamilies';
import { lookupLocaleMessage } from './localizationContract';

describe('primary Admin readiness i18n', () => {
  it('covers every reachable item/status label, summary, and next action in priority locales', () => {
    const priorityLocales = ['en', 'es', 'fr', 'ru', 'ar', 'zh-Hans'] as const;
    for (const locale of priorityLocales) {
      const messages = localeResources[locale].translation;
      for (const [item, statuses] of Object.entries(
        deploymentReadinessStatuses
      )) {
        expect(
          lookupLocaleMessage(
            messages,
            `adminDeployment.readiness.${item}.label`
          ),
          `${locale} ${item} label`
        ).toBeTypeOf('string');
        for (const status of statuses) {
          for (const field of ['summary', 'nextAction'] as const) {
            expect(
              lookupLocaleMessage(
                messages,
                `adminDeployment.readiness.${item}.status.${status}.${field}`
              ),
              `${locale} ${item}/${status}/${field}`
            ).toBeTypeOf('string');
          }
        }
      }
    }
  });

  it('resolves readiness, wizard, and Instance default labels without leaking placeholders', async () => {
    const previousLanguage = i18n.language;
    await i18n.changeLanguage('en');

    try {
      const rendered = [
        i18n.t('adminDeployment.readiness.statusTitle', { status: 'Blocked' }),
        i18n.t('adminDeployment.readiness.blockerCount', { count: 2 }),
        i18n.t('adminDeployment.readiness.warningCount', { count: 3 }),
        i18n.t(
          'adminDeployment.readiness.restart_required.status.restart_required.summary',
          { changedSettings: 'LLM_MODEL, FRONTEND_URL' }
        ),
        i18n.t('adminDeployment.wizard.step', { current: 1, total: 4 }),
        i18n.t('admin.instanceConfig.defaultLanguageLabel'),
        i18n.t('admin.instanceConfig.defaultThemeLabel'),
        i18n.t('language.spanish'),
      ];

      expect(rendered).toContain('Deployment Readiness: Blocked');
      expect(rendered).toContain('2 blockers');
      expect(rendered).toContain('3 warnings');
      expect(rendered).toContain(
        'Restart-required Deployment Settings changed after service start. (LLM_MODEL, FRONTEND_URL)'
      );
      expect(rendered).toContain('Step 1 of 4');
      for (const value of rendered) {
        expect(value).not.toMatch(/\{\{|\}\}/);
        expect(value).not.toMatch(/^admin\.|^language\./);
      }
    } finally {
      await i18n.changeLanguage(previousLanguage);
    }
  });
});
