import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  LANGUAGES,
  STORAGE_KEY_LANGUAGE,
  STORAGE_KEY_LANGUAGE_EXPLICIT,
  getExplicitLanguageChoice,
  hasChosenLanguage,
  saveExplicitLanguageChoice,
} from './languages';

describe('language priority and explicit choice', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps the six priority languages at the top in product order', () => {
    expect(LANGUAGES.slice(0, 6).map(({ code }) => code)).toEqual([
      'es',
      'en',
      'fr',
      'ru',
      'ar',
      'zh-Hans',
    ]);
  });

  it('records and reads an explicit language choice', () => {
    const getItem = vi.mocked(localStorage.getItem);
    const setItem = vi.mocked(localStorage.setItem);
    getItem.mockReturnValue('1');

    saveExplicitLanguageChoice('es');

    expect(setItem).toHaveBeenCalledWith(STORAGE_KEY_LANGUAGE, 'es');
    expect(setItem).toHaveBeenCalledWith(STORAGE_KEY_LANGUAGE_EXPLICIT, '1');
    expect(hasChosenLanguage()).toBe(true);
  });

  it('does not treat an unmarked legacy language as an explicit choice', () => {
    const getItem = vi.mocked(localStorage.getItem);
    const setItem = vi.mocked(localStorage.setItem);
    getItem.mockImplementation((key: string) =>
      key === STORAGE_KEY_LANGUAGE ? 'fr' : null
    );

    expect(hasChosenLanguage()).toBe(false);
    expect(setItem).not.toHaveBeenCalled();
  });

  it('does not treat an invalid legacy language as an explicit choice', () => {
    const getItem = vi.mocked(localStorage.getItem);
    getItem.mockImplementation((key: string) =>
      key === STORAGE_KEY_LANGUAGE ? 'xx-Unknown' : null
    );

    expect(hasChosenLanguage()).toBe(false);
  });

  it('does not promote an unmarked legacy language into a request locale', () => {
    const getItem = vi.mocked(localStorage.getItem);
    const setItem = vi.mocked(localStorage.setItem);
    getItem.mockImplementation((key: string) =>
      key === STORAGE_KEY_LANGUAGE ? 'es' : null
    );

    expect(getExplicitLanguageChoice()).toBeUndefined();
    expect(setItem).not.toHaveBeenCalled();
  });

  it('requires the explicit-choice marker for request propagation', () => {
    const getItem = vi.mocked(localStorage.getItem);
    getItem.mockImplementation((key: string) => {
      if (key === STORAGE_KEY_LANGUAGE) return 'es';
      if (key === STORAGE_KEY_LANGUAGE_EXPLICIT) return '0';
      return null;
    });

    expect(getExplicitLanguageChoice()).toBeUndefined();
  });

  it('returns only a valid explicit locale for request propagation', () => {
    const getItem = vi.mocked(localStorage.getItem);
    expect(getExplicitLanguageChoice()).toBeUndefined();

    getItem.mockImplementation((key: string) => {
      if (key === STORAGE_KEY_LANGUAGE) return 'xx-Unknown';
      if (key === STORAGE_KEY_LANGUAGE_EXPLICIT) return '1';
      return null;
    });

    expect(getExplicitLanguageChoice()).toBeUndefined();

    getItem.mockImplementation((key: string) => {
      if (key === STORAGE_KEY_LANGUAGE) return 'es';
      if (key === STORAGE_KEY_LANGUAGE_EXPLICIT) return '1';
      return null;
    });

    expect(getExplicitLanguageChoice()).toBe('es');
  });
});
