import { describe, expect, it } from 'vitest';
import { resolveAdminApplyIntent } from './adminApplyIntent';

describe('resolveAdminApplyIntent', () => {
  it('treats short apply commands as unambiguous when a pending change set exists', () => {
    expect(resolveAdminApplyIntent('Apply them', true)).toEqual({
      kind: 'unambiguous',
    });
    expect(resolveAdminApplyIntent('apply', true)).toEqual({
      kind: 'unambiguous',
    });
    expect(resolveAdminApplyIntent('Go ahead and apply', true)).toEqual({
      kind: 'unambiguous',
    });
    expect(resolveAdminApplyIntent('Please apply changes', true)).toEqual({
      kind: 'unambiguous',
    });
  });

  it('treats broader apply language as ambiguous when a pending change set exists', () => {
    expect(
      resolveAdminApplyIntent(
        'Apply the theme changes we discussed earlier',
        true
      )
    ).toEqual({
      kind: 'ambiguous',
    });
    expect(
      resolveAdminApplyIntent('Can you confirm the deployment updates?', true)
    ).toEqual({
      kind: 'ambiguous',
    });
  });

  it('treats apply language as ambiguous when no pending change set exists', () => {
    expect(resolveAdminApplyIntent('Apply them', false)).toEqual({
      kind: 'ambiguous',
    });
    expect(
      resolveAdminApplyIntent('Please apply the new settings', false)
    ).toEqual({
      kind: 'ambiguous',
    });
  });

  it('ignores unrelated admin messages', () => {
    expect(
      resolveAdminApplyIntent('What is the current primary color?', true)
    ).toEqual({
      kind: 'none',
    });
    expect(resolveAdminApplyIntent('Show deployment health', false)).toEqual({
      kind: 'none',
    });
  });
});
