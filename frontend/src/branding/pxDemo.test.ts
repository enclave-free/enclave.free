import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
  localStorage.clear();
  document.head
    .querySelectorAll('[data-instance-branding]')
    .forEach((el) => el.remove());
});

describe('temporary PX document branding', () => {
  it('overrides only presentation and does not overwrite cached instance settings', async () => {
    vi.stubEnv('VITE_DEMO_BRAND', 'wlc');
    vi.resetModules();
    const { applyDocumentTitle, applyFavicon } = await import('./pxDocument');
    const { saveInstanceConfig, getInstanceConfig, DEFAULT_INSTANCE_CONFIG } =
      await import('../types/instance');
    const original = {
      ...DEFAULT_INSTANCE_CONFIG,
      name: 'Original instance',
      faviconUrl: '/original.svg',
    };
    saveInstanceConfig(original);
    const before = localStorage.getItem('enclave_instance_config');
    applyDocumentTitle(original.name);
    applyFavicon(original.faviconUrl);
    expect(document.title).toBe('LIBERATOR');
    expect(
      document.querySelector('link[rel="icon"]')?.getAttribute('href')
    ).toBe('/demo-branding/liberator.svg');
    expect(localStorage.getItem('enclave_instance_config')).toBe(before);
    expect(getInstanceConfig().name).toBe('Original instance');
  });

  it('restores original title and removes the demo favicon when disabled', async () => {
    vi.stubEnv('VITE_DEMO_BRAND', 'wlc');
    vi.resetModules();
    const enabled = await import('./pxDocument');
    enabled.applyDocumentTitle('Original');
    enabled.applyFavicon('');
    vi.stubEnv('VITE_DEMO_BRAND', '');
    vi.resetModules();
    const disabled = await import('./pxDocument');
    disabled.applyDocumentTitle('Original');
    disabled.applyFavicon('');
    expect(document.title).toBe('Original');
    expect(document.querySelector('link[rel="icon"]')).toBeNull();
  });
});
