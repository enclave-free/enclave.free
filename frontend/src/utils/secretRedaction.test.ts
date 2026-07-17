import { describe, expect, it } from 'vitest';
import { redactSecrets } from './secretRedaction';

describe('redactSecrets', () => {
  it('redacts known long secrets without touching short ordinary values', () => {
    expect(
      redactSecrets('token=long-secret-value status=ok', [
        'long-secret-value',
        'ok',
      ])
    ).toBe('token=[REDACTED] status=ok');
  });

  it('redacts longer overlapping values first', () => {
    expect(
      redactSecrets('mysecretkey123', ['secretkey', 'mysecretkey123'])
    ).toBe('[REDACTED]');
  });
});
