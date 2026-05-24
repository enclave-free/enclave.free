import type { AdminAssistantChangeSet } from '../../utils/adminAssistant';

export type AdminChangeConfirmationState =
  | { state: 'idle' }
  | {
      state: 'review';
      changeSet: AdminAssistantChangeSet;
      supersededChangeSet?: AdminAssistantChangeSet;
    }
  | { state: 'applying'; changeSet: AdminAssistantChangeSet }
  | { state: 'applied'; changeSet: AdminAssistantChangeSet; message: string }
  | { state: 'rejected'; changeSet: AdminAssistantChangeSet }
  | { state: 'error'; changeSet?: AdminAssistantChangeSet; message: string };

export type AdminChangeConfirmationAction =
  | { type: 'changeSetReadyForReview'; changeSet: AdminAssistantChangeSet }
  | { type: 'applyStarted' }
  | { type: 'applySucceeded'; message: string }
  | { type: 'applyFailed'; message: string }
  | { type: 'parseFailed'; message: string }
  | { type: 'adminConfigToolToggled'; selectedAfterToggle: boolean }
  | { type: 'newConversationStarted' }
  | { type: 'dismissed' }
  | { type: 'rejected' };

export interface AdminChangePreview {
  summary: string;
  requests: Array<{
    idx: number;
    method: string;
    path: string;
    body: unknown;
  }>;
}

export function createAdminChangeConfirmationState(): AdminChangeConfirmationState {
  return { state: 'idle' };
}

export function reduceAdminChangeConfirmationState(
  state: AdminChangeConfirmationState,
  action: AdminChangeConfirmationAction
): AdminChangeConfirmationState {
  switch (action.type) {
    case 'changeSetReadyForReview':
      return {
        state: 'review',
        changeSet: action.changeSet,
        ...(state.state === 'review' || state.state === 'applying'
          ? { supersededChangeSet: state.changeSet }
          : {}),
      };
    case 'applyStarted':
      return state.state === 'review' || state.state === 'applying'
        ? { state: 'applying', changeSet: state.changeSet }
        : state;
    case 'applySucceeded':
      return state.state === 'applying'
        ? {
            state: 'applied',
            changeSet: state.changeSet,
            message: action.message,
          }
        : state;
    case 'applyFailed':
      return state.state === 'applying' || state.state === 'review'
        ? {
            state: 'error',
            changeSet: state.changeSet,
            message: action.message,
          }
        : state;
    case 'parseFailed':
      return { state: 'error', message: action.message };
    case 'rejected':
      return state.state === 'review' || state.state === 'applying'
        ? { state: 'rejected', changeSet: state.changeSet }
        : state;
    case 'adminConfigToolToggled':
      return action.selectedAfterToggle ? state : { state: 'idle' };
    case 'newConversationStarted':
    case 'dismissed':
      return { state: 'idle' };
  }
}

export function buildAdminChangePreview(
  changeSet: AdminAssistantChangeSet,
  options: {
    deploymentSecretKeysLoaded: boolean;
    deploymentSecretKeys: Set<string>;
  }
): AdminChangePreview {
  return {
    summary: changeSet.summary || '',
    requests: changeSet.requests.map((request, index) => ({
      idx: index + 1,
      method: request.method,
      path: request.path,
      body: maskDeploymentSecretBody(request.path, request.body, options),
    })),
  };
}

function maskDeploymentSecretBody(
  path: string,
  body: unknown,
  options: {
    deploymentSecretKeysLoaded: boolean;
    deploymentSecretKeys: Set<string>;
  }
): unknown {
  if (!path.startsWith('/admin/deployment/config/')) return body;
  const key = path.split('/').pop() || '';
  const shouldRedact =
    !options.deploymentSecretKeysLoaded ||
    options.deploymentSecretKeys.has(key) ||
    /SECRET|TOKEN|KEY|PASSWORD/i.test(key);
  if (!shouldRedact || !body || typeof body !== 'object' || Array.isArray(body))
    return body;

  const objectBody = body as Record<string, unknown>;
  if (typeof objectBody.value === 'string' && objectBody.value.length > 0) {
    return { ...objectBody, value: '[REDACTED]' };
  }
  return body;
}
