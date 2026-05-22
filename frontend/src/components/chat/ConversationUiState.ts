import type { ConversationActivityStep, ConversationTrace } from './ChatMessage'

export interface ConversationControlSnapshot {
  selectedTools: string[]
  selectedDocuments: string[]
}

export interface ConversationUiTurn {
  id: string
  role: 'user' | 'assistant'
  content: string
  activitySteps: ConversationActivityStep[]
  trace: ConversationTrace | null
  traceStatus: string | null
  controlSnapshot?: ConversationControlSnapshot
}

export interface ConversationUiState {
  turns: ConversationUiTurn[]
  selectedTools: string[]
  selectedDocuments: string[]
  isRunning: boolean
  error: string | null
  conversationSessionId: string | null
}

export type ConversationUiAction =
  | {
      type: 'userTurnSubmitted'
      id: string
      content: string
    }
  | {
      type: 'assistantTurnStarted'
      id: string
      sessionId?: string | null
      traceStatus?: string | null
    }
  | {
      type: 'assistantActivityStepReceived'
      assistantTurnId: string
      step: ConversationActivityStep
    }
  | {
      type: 'assistantTraceStatusChanged'
      assistantTurnId: string
      traceStatus: string
    }
  | {
      type: 'assistantContentDeltaReceived'
      assistantTurnId: string
      delta: string
    }
  | {
      type: 'assistantContentReplaced'
      assistantTurnId: string
      content: string
    }
  | {
      type: 'assistantTraceSettled'
      assistantTurnId: string
      trace: ConversationTrace
    }
  | {
      type: 'assistantTurnFinished'
      sessionId?: string | null
    }
  | {
      type: 'assistantTurnFailed'
      assistantTurnId: string
      message: string
    }
  | {
      type: 'requestFailed'
      message: string
    }
  | {
      type: 'requestErrorDismissed'
    }
  | {
      type: 'toolToggled'
      toolId: string
    }
  | {
      type: 'documentToggled'
      documentId: string
    }
  | {
      type: 'newConversationStarted'
    }
  | {
      type: 'selectedToolsChanged'
      selectedTools: string[]
    }
  | {
      type: 'selectedDocumentsChanged'
      selectedDocuments: string[]
    }
  | {
      type: 'conversationSessionChanged'
      sessionId: string | null
    }
  | {
      type: 'assistantTurnCompleted'
      id: string
      content: string
      trace?: ConversationTrace | null
      sessionId?: string | null
    }
  | {
      type: 'assistantTurnAppended'
      id: string
      content: string
    }
  | {
      type: 'assistantTurnsRemovedByContentPrefix'
      prefix: string
    }

export function createConversationUiState(
  initial: Partial<Pick<ConversationUiState, 'selectedTools' | 'selectedDocuments' | 'conversationSessionId'>> = {}
): ConversationUiState {
  return {
    turns: [],
    selectedTools: initial.selectedTools ?? [],
    selectedDocuments: initial.selectedDocuments ?? [],
    isRunning: false,
    error: null,
    conversationSessionId: initial.conversationSessionId ?? null,
  }
}

export function reduceConversationUiState(
  state: ConversationUiState,
  action: ConversationUiAction
): ConversationUiState {
  switch (action.type) {
    case 'userTurnSubmitted':
      return {
        ...state,
        turns: [
          ...state.turns,
          {
            id: action.id,
            role: 'user',
            content: action.content,
            activitySteps: [],
            trace: null,
            traceStatus: null,
            controlSnapshot: {
              selectedTools: [...state.selectedTools],
              selectedDocuments: [...state.selectedDocuments],
            },
          },
        ],
        isRunning: true,
        error: null,
      }
    case 'assistantTurnStarted':
      return {
        ...state,
        turns: [
          ...state.turns,
          {
            id: action.id,
            role: 'assistant',
            content: '',
            activitySteps: [],
            trace: null,
            traceStatus: action.traceStatus ?? null,
          },
        ],
        isRunning: true,
        error: null,
        conversationSessionId: action.sessionId ?? state.conversationSessionId,
      }
    case 'assistantActivityStepReceived':
      return updateAssistantTurn(state, action.assistantTurnId, (turn) => ({
        ...turn,
        activitySteps: mergeActivitySteps(turn.activitySteps, [action.step]),
      }))
    case 'assistantTraceStatusChanged':
      return updateAssistantTurn(state, action.assistantTurnId, (turn) => ({
        ...turn,
        traceStatus: action.traceStatus,
      }))
    case 'assistantContentDeltaReceived':
      return updateAssistantTurn(state, action.assistantTurnId, (turn) => ({
        ...turn,
        content: `${turn.content}${action.delta}`,
      }))
    case 'assistantContentReplaced':
      return updateAssistantTurn(state, action.assistantTurnId, (turn) => ({
        ...turn,
        content: action.content,
      }))
    case 'assistantTraceSettled':
      return updateAssistantTurn(state, action.assistantTurnId, (turn) => ({
        ...turn,
        trace: action.trace,
        traceStatus: null,
        activitySteps: mergeActivitySteps(turn.activitySteps, action.trace.activity_steps ?? []),
      }))
    case 'assistantTurnFinished':
      return {
        ...state,
        isRunning: false,
        conversationSessionId: action.sessionId ?? state.conversationSessionId,
        turns: state.turns.map((turn) => (
          turn.role === 'assistant' ? { ...turn, traceStatus: null } : turn
        )),
      }
    case 'assistantTurnFailed':
      return {
        ...state,
        isRunning: false,
        error: action.message,
        turns: state.turns
          .map((turn) => (
            turn.id === action.assistantTurnId && turn.role === 'assistant'
              ? { ...turn, traceStatus: null }
              : turn
          ))
          .filter((turn) => (
            turn.id !== action.assistantTurnId ||
            turn.role !== 'assistant' ||
            turn.content.trim() ||
            turn.activitySteps.length > 0 ||
            turn.trace
          )),
      }
    case 'requestFailed':
      return {
        ...state,
        isRunning: false,
        error: action.message,
      }
    case 'requestErrorDismissed':
      return {
        ...state,
        error: null,
      }
    case 'toolToggled':
      return {
        ...state,
        selectedTools: toggleValue(state.selectedTools, action.toolId),
      }
    case 'documentToggled':
      return {
        ...state,
        selectedDocuments: toggleValue(state.selectedDocuments, action.documentId),
      }
    case 'newConversationStarted':
      return {
        ...state,
        turns: [],
        isRunning: false,
        error: null,
        conversationSessionId: null,
      }
    case 'selectedToolsChanged':
      return {
        ...state,
        selectedTools: [...action.selectedTools],
      }
    case 'selectedDocumentsChanged':
      return {
        ...state,
        selectedDocuments: [...action.selectedDocuments],
      }
    case 'conversationSessionChanged':
      return {
        ...state,
        conversationSessionId: action.sessionId,
      }
    case 'assistantTurnCompleted':
      return {
        ...state,
        turns: [
          ...state.turns,
          {
            id: action.id,
            role: 'assistant',
            content: action.content,
            activitySteps: [],
            trace: action.trace ?? null,
            traceStatus: null,
          },
        ],
        isRunning: false,
        conversationSessionId: action.sessionId ?? state.conversationSessionId,
      }
    case 'assistantTurnAppended':
      return {
        ...state,
        turns: [
          ...state.turns,
          {
            id: action.id,
            role: 'assistant',
            content: action.content,
            activitySteps: [],
            trace: null,
            traceStatus: null,
          },
        ],
      }
    case 'assistantTurnsRemovedByContentPrefix':
      return {
        ...state,
        turns: state.turns.filter((turn) => !turn.content.startsWith(action.prefix)),
      }
  }
}

function updateAssistantTurn(
  state: ConversationUiState,
  assistantTurnId: string,
  update: (turn: ConversationUiTurn) => ConversationUiTurn
): ConversationUiState {
  return {
    ...state,
    turns: state.turns.map((turn) => (
      turn.id === assistantTurnId && turn.role === 'assistant' ? update(turn) : turn
    )),
  }
}

function mergeActivitySteps(
  existing: ConversationActivityStep[],
  incoming: ConversationActivityStep[]
): ConversationActivityStep[] {
  const merged = new Map<string, ConversationActivityStep>()
  for (const step of existing) merged.set(step.id, step)
  for (const step of incoming) merged.set(step.id, step)
  return Array.from(merged.values())
}

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value)
    ? values.filter((existing) => existing !== value)
    : [...values, value]
}
