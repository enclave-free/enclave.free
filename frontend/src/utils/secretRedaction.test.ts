import { describe, expect, it } from 'vitest';
import { redactSecrets } from './secretRedaction';

describe('redactSecrets', () => {
  it('redacts every known non-empty secret, including short values', () => {
    expect(
      redactSecrets('token=long-secret-value status=xy', [
        'long-secret-value',
        'xy',
      ])
    ).toBe('token=[REDACTED] status=[REDACTED]');
  });

  it('redacts longer overlapping values first', () => {
    expect(
      redactSecrets('mysecretkey123', ['secretkey', 'mysecretkey123'])
    ).toBe('[REDACTED]');
  });
});
