import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import {
  STORAGE_KEY_LANGUAGE,
  STORAGE_KEY_LANGUAGE_EXPLICIT,
} from '../../utils/languages';
import { LanguageSwitcher } from './LanguageSwitcher';

describe('LanguageSwitcher', () => {
  beforeEach(async () => {
    localStorage.clear();
    await i18n.changeLanguage('en');
  });

  afterEach(async () => {
    cleanup();
    vi.restoreAllMocks();
    localStorage.clear();
    await i18n.changeLanguage('en');
  });

  it('falls back to English when i18n reports an unknown language', async () => {
    await i18n.changeLanguage('xx-Unknown');

    render(<LanguageSwitcher />);

    expect(
      screen.getByRole('button', { name: 'Change language' })
    ).toHaveTextContent('English');
  });

  it('persists both the selected language and explicit-choice marker', async () => {
    const user = userEvent.setup();
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    render(<LanguageSwitcher />);

    await user.click(screen.getByRole('button', { name: 'Change language' }));
    await user.click(screen.getByRole('menuitemradio', { name: 'Español' }));

    expect(setItem).toHaveBeenCalledWith(STORAGE_KEY_LANGUAGE, 'es');
    expect(setItem).toHaveBeenCalledWith(STORAGE_KEY_LANGUAGE_EXPLICIT, '1');
  });

  it('still changes the active language when storage is unavailable', async () => {
    const user = userEvent.setup();
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage unavailable');
    });
    const changeLanguage = vi.spyOn(i18n, 'changeLanguage');
    render(<LanguageSwitcher />);

    await user.click(screen.getByRole('button', { name: 'Change language' }));
    await user.click(screen.getByRole('menuitemradio', { name: 'Español' }));

    expect(changeLanguage).toHaveBeenCalledWith('es');
  });
});
