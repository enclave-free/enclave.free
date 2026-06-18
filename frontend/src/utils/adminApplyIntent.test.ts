import { describe, expect, it } from 'vitest';
import { resolveAdminApplyIntent } from './adminApplyIntent';

describe('resolveAdminApplyIntent', () => {
  it('routes apply language to the pending panel when a change set exists', () => {
    expect(resolveAdminApplyIntent('Apply them', true)).toEqual({
      kind: 'needs-panel',
    });
    expect(resolveAdminApplyIntent('apply', true)).toEqual({
      kind: 'needs-panel',
    });
    expect(resolveAdminApplyIntent('Go ahead and apply', true)).toEqual({
      kind: 'needs-panel',
    });
    expect(resolveAdminApplyIntent('Please apply changes', true)).toEqual({
      kind: 'needs-panel',
    });
    expect(resolveAdminApplyIntent('I confirm', true)).toEqual({
      kind: 'needs-panel',
    });
    expect(resolveAdminApplyIntent('yes do it', true)).toEqual({
      kind: 'needs-panel',
    });
    expect(resolveAdminApplyIntent('do it', true)).toEqual({
      kind: 'needs-panel',
    });
    expect(
      resolveAdminApplyIntent(
        'Apply the theme changes we discussed earlier',
        true
      )
    ).toEqual({
      kind: 'needs-panel',
    });
  });

  it('lets broader apply or confirm questions continue to Sage even when a change set exists', () => {
    expect(
      resolveAdminApplyIntent('Can you confirm the deployment updates?', true)
    ).toEqual({
      kind: 'none',
    });
  });

  it('lets apply language continue to Sage when no change set exists', () => {
    expect(resolveAdminApplyIntent('Apply them', false)).toEqual({
      kind: 'none',
    });
    expect(
      resolveAdminApplyIntent('Please apply the new settings', false)
    ).toEqual({
      kind: 'none',
    });
    expect(resolveAdminApplyIntent('I confirm', false)).toEqual({
      kind: 'none',
    });
    expect(
      resolveAdminApplyIntent(
        'I confirm: "Greeting: update greeting. Tone: update tone."',
        false
      )
    ).toEqual({
      kind: 'none',
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
