import {
  finalizeEvent,
  getPublicKey,
  nip04,
  type EventTemplate,
} from 'nostr-tools';
import type { WindowNostr } from 'nostr-tools/nip07';

const DEV_NOSTR_QUERY_PARAM = 'dev_nostr';
const DEFAULT_DEV_NOSTR_SECRET_KEY_HEX =
  '1111111111111111111111111111111111111111111111111111111111111111';

function hexToBytes(hex: string): Uint8Array | null {
  const normalized = hex.trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(normalized)) {
    return null;
  }

  const bytes = new Uint8Array(32);
  for (let i = 0; i < bytes.length; i += 1) {
    bytes[i] = Number.parseInt(normalized.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

function isLocalDevelopmentHost(hostname: string): boolean {
  return (
    hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
  );
}

function isDevelopmentNostrRequested(): boolean {
  const params = new URLSearchParams(window.location.search);
  return (
    params.get(DEV_NOSTR_QUERY_PARAM) === '1' ||
    import.meta.env.VITE_ENABLE_DEV_NOSTR === 'true'
  );
}

function getDevelopmentSecretKey(): Uint8Array | null {
  return hexToBytes(
    import.meta.env.VITE_DEV_NOSTR_PRIVATE_KEY_HEX ||
      DEFAULT_DEV_NOSTR_SECRET_KEY_HEX
  );
}

function createDevelopmentNostr(secretKey: Uint8Array): WindowNostr {
  const pubkey = getPublicKey(secretKey);

  return {
    getPublicKey: async () => pubkey,
    signEvent: async (event: EventTemplate) =>
      finalizeEvent(
        {
          ...event,
          tags: event.tags.map((tag) => [...tag]),
        },
        secretKey
      ),
    nip04: {
      encrypt: async (targetPubkey, plaintext) =>
        nip04.encrypt(secretKey, targetPubkey, plaintext),
      decrypt: async (sourcePubkey, ciphertext) =>
        nip04.decrypt(secretKey, sourcePubkey, ciphertext),
    },
  };
}

export function installDevelopmentNostrExtensionForSmokeTests(): boolean {
  if (!import.meta.env.DEV || typeof window === 'undefined') {
    return false;
  }

  if (window.nostr) {
    return false;
  }

  if (
    !isLocalDevelopmentHost(window.location.hostname) ||
    !isDevelopmentNostrRequested()
  ) {
    return false;
  }

  const secretKey = getDevelopmentSecretKey();
  if (!secretKey) {
    console.warn(
      'Invalid VITE_DEV_NOSTR_PRIVATE_KEY_HEX; development NIP-07 shim disabled'
    );
    return false;
  }

  window.nostr = createDevelopmentNostr(secretKey);
  return true;
}
