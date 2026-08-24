import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { DecryptProgressInline, DecryptStatus } from './DecryptStatus';
import { decryptField } from '../../utils/encryption';

describe('DecryptStatus', () => {
  let release: Array<() => void>;

  beforeEach(() => {
    release = [];
    // Hold each decrypt open so the indicator's active window is observable.
    const decrypt = vi.fn(
      () =>
        new Promise<string>((resolve) => {
          release.push(() => resolve('plain'));
        })
    );
    // @ts-expect-error -- minimal NIP-07 shim
    window.nostr = { nip04: { decrypt } };
  });

  afterEach(() => {
    // This suite does not configure global auto-cleanup, so unmount explicitly
    // or a second render leaves two status regions in the DOM.
    cleanup();
    delete (window as { nostr?: unknown }).nostr;
    vi.restoreAllMocks();
  });

  const field = (n: number) => ({
    ciphertext: `c${n}`,
    ephemeral_pubkey: `p${n}`,
  });

  it('stays hidden while nothing is decrypting', () => {
    render(<DecryptStatus />);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('reports the pending count and clears when the queue drains', async () => {
    render(<DecryptStatus />);

    const pending = Promise.all([
      decryptField(field(1)),
      decryptField(field(2)),
      decryptField(field(3)),
    ]);

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Decrypting 0 of 3'
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'check your Nostr extension'
    );
    // Serial requests still prompt per field unless the Admin picks a
    // persistent approval, so the guidance has to be here. Wording stays
    // generic rather than naming one extension's button. See #648.
    expect(screen.getByRole('status')).toHaveTextContent(
      'Choose the remember or always option so it only asks once.'
    );

    // Let them through one at a time; the queue is serial.
    for (let i = 0; i < 3; i += 1) {
      await waitFor(() => expect(release.length).toBeGreaterThan(i));
      release[i]();
    }
    await pending;

    await waitFor(() =>
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    );
  });

  it('shows the same persistent-approval guidance on the inline variant', async () => {
    render(<DecryptProgressInline />);

    const pending = decryptField(field(1));
    const status = await screen.findByRole('status');

    expect(status).toHaveTextContent('Decrypting 0 of 1');
    expect(status).toHaveTextContent(
      'Choose the remember or always option so it only asks once.'
    );

    await waitFor(() => expect(release.length).toBeGreaterThan(0));
    release[0]();
    await pending;
  });
});
