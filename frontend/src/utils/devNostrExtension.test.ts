import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { verifyEvent } from 'nostr-tools';
import { createAuthEvent, hasNostrExtension } from './nostrAuth';
import { installDevelopmentNostrExtensionForSmokeTests } from './devNostrExtension';

describe('development NIP-07 smoke-test extension', () => {
  const originalLocation = window.location.href;

  beforeEach(() => {
    delete window.nostr;
    window.history.pushState({}, '', '/admin');
  });

  afterEach(() => {
    delete window.nostr;
    window.history.pushState({}, '', originalLocation);
  });

  it('does not install without an explicit local smoke-test opt-in', () => {
    const installed = installDevelopmentNostrExtensionForSmokeTests();

    expect(installed).toBe(false);
    expect(hasNostrExtension()).toBe(false);
  });

  it('installs a working NIP-07 surface for local smoke tests', async () => {
    window.history.pushState({}, '', '/admin?dev_nostr=1');

    const installed = installDevelopmentNostrExtensionForSmokeTests();
    const pubkey = await window.nostr?.getPublicKey();
    const signedEvent = await window.nostr?.signEvent(createAuthEvent());

    expect(installed).toBe(true);
    expect(hasNostrExtension()).toBe(true);
    expect(pubkey).toMatch(/^[0-9a-f]{64}$/);
    expect(signedEvent).toMatchObject({
      kind: 22242,
      tags: [['action', 'admin_auth']],
      content: '',
      pubkey,
    });
    expect(signedEvent?.id).toMatch(/^[0-9a-f]{64}$/);
    expect(signedEvent?.sig).toMatch(/^[0-9a-f]{128}$/);
    expect(signedEvent && verifyEvent(signedEvent)).toBe(true);
  });

  it('supports NIP-04 encryption and decryption with the same dev key', async () => {
    window.history.pushState({}, '', '/admin?dev_nostr=1');

    installDevelopmentNostrExtensionForSmokeTests();
    const pubkey = await window.nostr?.getPublicKey();
    const ciphertext = await window.nostr?.nip04?.encrypt(
      pubkey!,
      'secret value'
    );
    const plaintext = await window.nostr?.nip04?.decrypt(pubkey!, ciphertext!);

    expect(ciphertext).toBeTruthy();
    expect(plaintext).toBe('secret value');
  });
});
