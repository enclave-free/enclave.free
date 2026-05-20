import { describe, expect, it } from 'vitest'
import i18n from './index'

describe('primary Admin readiness i18n', () => {
  it('resolves readiness, wizard, and Instance default labels without leaking placeholders', async () => {
    const previousLanguage = i18n.language
    await i18n.changeLanguage('en')

    try {
      const rendered = [
        i18n.t('adminDeployment.readiness.statusTitle', { status: 'Blocked' }),
        i18n.t('adminDeployment.readiness.blockerCount', { count: 2 }),
        i18n.t('adminDeployment.readiness.warningCount', { count: 3 }),
        i18n.t('adminDeployment.wizard.step', { current: 1, total: 4 }),
        i18n.t('admin.instanceConfig.defaultLanguageLabel'),
        i18n.t('admin.instanceConfig.defaultThemeLabel'),
        i18n.t('language.spanish'),
      ]

      expect(rendered).toContain('Deployment Readiness: Blocked')
      expect(rendered).toContain('2 blockers')
      expect(rendered).toContain('3 warnings')
      expect(rendered).toContain('Step 1 of 4')
      for (const value of rendered) {
        expect(value).not.toMatch(/\{\{|\}\}/)
        expect(value).not.toMatch(/^admin\.|^language\./)
      }
    } finally {
      await i18n.changeLanguage(previousLanguage)
    }
  })
})
