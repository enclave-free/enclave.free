import { describe, expect, it } from 'vitest';
import {
  buildAdminChangePreview,
  createAdminChangeConfirmationState,
  reduceAdminChangeConfirmationState,
} from './AdminChangeConfirmationState';
import type { AdminAssistantChangeSet } from '../../utils/adminAssistant';

const changeSet: AdminAssistantChangeSet = {
  version: 1,
  summary: 'Update provider key',
  requests: [
    {
      method: 'PUT',
      path: '/admin/deployment/config/TINFOIL_API_KEY',
      body: { value: 'secret-value' },
    },
  ],
};

const newerChangeSet: AdminAssistantChangeSet = {
  version: 1,
  summary: 'Update instance theme',
  requests: [
    {
      method: 'PUT',
      path: '/admin/settings',
      body: { primary_color: '#1E3A8A' },
    },
  ],
};

describe('Admin Change Confirmation State', () => {
  it('tracks review, applying, applied, and error states separately from shared Conversation UI State', () => {
    const review = reduceAdminChangeConfirmationState(
      createAdminChangeConfirmationState(),
      {
        type: 'changeSetReadyForReview',
        changeSet,
      }
    );
    expect(review).toEqual({ state: 'review', changeSet });

    const applying = reduceAdminChangeConfirmationState(review, {
      type: 'applyStarted',
    });
    expect(applying).toEqual({ state: 'applying', changeSet });

    const applied = reduceAdminChangeConfirmationState(applying, {
      type: 'applySucceeded',
      message: 'Applied 1 change',
    });
    expect(applied).toEqual({
      state: 'applied',
      changeSet,
      message: 'Applied 1 change',
    });

    const error = reduceAdminChangeConfirmationState(applying, {
      type: 'applyFailed',
      message: 'Config validation failed',
    });
    expect(error).toEqual({
      state: 'error',
      changeSet,
      message: 'Config validation failed',
    });
  });

  it('clears pending confirmation when admin-config is toggled off or a new Conversation starts', () => {
    const review = reduceAdminChangeConfirmationState(
      createAdminChangeConfirmationState(),
      {
        type: 'changeSetReadyForReview',
        changeSet,
      }
    );

    expect(
      reduceAdminChangeConfirmationState(review, {
        type: 'adminConfigToolToggled',
        selectedAfterToggle: false,
      })
    ).toEqual({ state: 'idle' });
    expect(
      reduceAdminChangeConfirmationState(review, {
        type: 'newConversationStarted',
      })
    ).toEqual({ state: 'idle' });
  });

  it('marks an older pending confirmation as superseded when a newer change set is staged', () => {
    const review = reduceAdminChangeConfirmationState(
      createAdminChangeConfirmationState(),
      {
        type: 'changeSetReadyForReview',
        changeSet,
      }
    );

    const superseded = reduceAdminChangeConfirmationState(review, {
      type: 'changeSetReadyForReview',
      changeSet: newerChangeSet,
    });

    expect(superseded).toEqual({
      state: 'review',
      changeSet: newerChangeSet,
      supersededChangeSet: changeSet,
    });
  });

  it('ignores late apply results after confirmation state has been cleared', () => {
    const review = reduceAdminChangeConfirmationState(
      createAdminChangeConfirmationState(),
      {
        type: 'changeSetReadyForReview',
        changeSet,
      }
    );
    const applying = reduceAdminChangeConfirmationState(review, {
      type: 'applyStarted',
    });
    const cleared = reduceAdminChangeConfirmationState(applying, {
      type: 'dismissed',
    });

    expect(
      reduceAdminChangeConfirmationState(cleared, {
        type: 'applySucceeded',
        message: 'Applied late',
      })
    ).toEqual({ state: 'idle' });
    expect(
      reduceAdminChangeConfirmationState(cleared, {
        type: 'applyFailed',
        message: 'Failed late',
      })
    ).toEqual({ state: 'idle' });
  });

  it('surfaces parse failures even when no confirmation card is active', () => {
    expect(
      reduceAdminChangeConfirmationState(createAdminChangeConfirmationState(), {
        type: 'parseFailed',
        message: 'Invalid change set',
      })
    ).toEqual({ state: 'error', message: 'Invalid change set' });
  });

  it('masks secret deployment config preview values pessimistically', () => {
    expect(
      buildAdminChangePreview(changeSet, {
        deploymentSecretKeysLoaded: false,
        deploymentSecretKeys: new Set(),
      })
    ).toEqual({
      summary: 'Update provider key',
      requests: [
        {
          idx: 1,
          method: 'PUT',
          path: '/admin/deployment/config/TINFOIL_API_KEY',
          body: { value: '[REDACTED]' },
        },
      ],
    });

    expect(
      buildAdminChangePreview(changeSet, {
        deploymentSecretKeysLoaded: true,
        deploymentSecretKeys: new Set(['TINFOIL_API_KEY']),
      }).requests[0].body
    ).toEqual({ value: '[REDACTED]' });

    expect(
      buildAdminChangePreview(changeSet, {
        deploymentSecretKeysLoaded: true,
        deploymentSecretKeys: new Set(),
      }).requests[0].body
    ).toEqual({ value: '[REDACTED]' });
  });
});
