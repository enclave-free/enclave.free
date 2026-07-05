import { API_BASE } from '../types/onboarding';
import {
  classifyProviderError,
  formatClassifiedProviderError,
} from './providerErrors';
import {
  buildAdminSignerDecryptedContext,
  type AdminSignerDecryptedContext,
} from './adminSignerContext';

interface SendLlmChatOptions {
  content: string;
  tools: string[];
  sessionId?: string | null;
  jobIds?: string[];
  conversationHistory?: Array<{ role: 'user' | 'assistant'; content: string }>;
  /**
   * Optional bearer token to authenticate AS a specific user (impersonation).
   * Sage prefers the Authorization bearer over the session cookie, so this scopes
   * just this request to the token's user without touching the admin cookie.
   */
  authToken?: string | null;
  /**
   * Admin-only opt-in for Database turns. When true, the browser may use the
   * Admin's NIP-04 signer to decrypt bounded context for this turn.
   */
  includeAdminSignerDecryptedContext?: boolean;
  adminSignerDecryptedContext?: AdminSignerDecryptedContext | null;
}

type ConversationHistoryMessage = NonNullable<
  SendLlmChatOptions['conversationHistory']
>[number];

interface SendLlmChatStreamOptions extends SendLlmChatOptions {
  onEvent: (event: string, data: unknown) => void;
}

async function buildUnifiedChatBody({
  content,
  tools,
  sessionId,
  jobIds,
  conversationHistory,
  includeAdminSignerDecryptedContext,
  adminSignerDecryptedContext,
}: SendLlmChatOptions): Promise<Record<string, unknown>> {
  const body: Record<string, unknown> = {
    message: content,
    tools,
  };
  if (sessionId) {
    body.session_id = sessionId;
  }
  const constrainedJobIds = (jobIds || []).filter(Boolean);
  if (constrainedJobIds.length > 0) {
    body.job_ids = constrainedJobIds;
  }
  const sageOwnsAdminConfigHistory =
    Boolean(sessionId) && tools.includes('admin-config');
  const recentHistory = normalizedConversationHistory(conversationHistory);
  if (sageOwnsAdminConfigHistory) {
    const confirmationHistory = recentHistory
      .filter(isAdminConfigApplySummary)
      .slice(-3);
    if (confirmationHistory.length > 0) {
      body.conversation_history = confirmationHistory;
    }
  } else if (recentHistory.length > 0) {
    body.conversation_history = recentHistory.slice(-8);
  }

  const clientDecryptedContext = await resolveAdminSignerDecryptedContext({
    tools,
    includeAdminSignerDecryptedContext,
    adminSignerDecryptedContext,
  });
  if (clientDecryptedContext) {
    body.client_decrypted_context = clientDecryptedContext;
  }

  return body;
}

async function resolveAdminSignerDecryptedContext({
  tools,
  includeAdminSignerDecryptedContext,
  adminSignerDecryptedContext,
}: Pick<
  SendLlmChatOptions,
  'tools' | 'includeAdminSignerDecryptedContext' | 'adminSignerDecryptedContext'
>): Promise<AdminSignerDecryptedContext | null> {
  if (!includeAdminSignerDecryptedContext || !tools.includes('db-query')) {
    return null;
  }
  if (adminSignerDecryptedContext !== undefined) {
    return adminSignerDecryptedContext;
  }
  try {
    return await buildAdminSignerDecryptedContext();
  } catch (error) {
    console.warn('Failed to build Admin signer-decrypted context:', error);
    return null;
  }
}

function normalizedConversationHistory(
  conversationHistory: SendLlmChatOptions['conversationHistory']
): ConversationHistoryMessage[] {
  return (conversationHistory || [])
    .filter(
      (message) =>
        (message.role === 'user' || message.role === 'assistant') &&
        typeof message.content === 'string' &&
        message.content.trim()
    )
    .map((message) => ({
      role: message.role,
      content: message.content.slice(0, 2000),
    }));
}

function isAdminConfigApplySummary(
  message: ConversationHistoryMessage
): boolean {
  if (message.role !== 'assistant') return false;

  const content = message.content.trim();
  return (
    (content.startsWith('Applied ') && content.includes('change(s)')) ||
    content.startsWith('The change set was applied successfully')
  );
}

export async function sendLlmChatWithUnifiedTools(
  options: SendLlmChatOptions
): Promise<Response> {
  const body = await buildUnifiedChatBody(options);

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (options.authToken) {
    headers.Authorization = `Bearer ${options.authToken}`;
  }

  return fetch(`${API_BASE}/llm/chat`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(body),
  });
}

export async function sendLlmChatStreamWithUnifiedTools({
  onEvent,
  ...options
}: SendLlmChatStreamOptions): Promise<void> {
  const body = await buildUnifiedChatBody(options);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  };
  if (options.authToken) {
    headers.Authorization = `Bearer ${options.authToken}`;
  }

  const response = await fetch(`${API_BASE}/llm/chat/stream`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }

  await readSseResponse(response, onEvent);
}

async function responseErrorMessage(response: Response): Promise<string> {
  const fallback = `HTTP ${response.status}`;
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = (await response.json()) as Record<string, unknown>;
      return formatProviderError(data, fallback);
    }
    const text = (await response.text()).trim();
    return formatProviderError(text, text || fallback);
  } catch {
    return fallback;
  }
}

function formatProviderError(raw: unknown, fallback: string): string {
  const classified = classifyProviderError(raw);
  if (classified.category === 'unknown' && !extractProviderDetail(raw)) {
    return fallback;
  }
  return formatClassifiedProviderError(classified);
}

function extractProviderDetail(raw: unknown): string {
  if (typeof raw === 'string') {
    return raw.trim();
  }
  if (raw && typeof raw === 'object') {
    const record = raw as Record<string, unknown>;
    for (const key of ['detail', 'message', 'error'] as const) {
      const value = record[key];
      if (typeof value === 'string' && value.trim()) {
        return value.trim();
      }
    }
  }
  return '';
}

async function readSseResponse(
  response: Response,
  onEvent: (event: string, data: unknown) => void
): Promise<void> {
  if (!response.body) {
    throw new Error('Streaming response body is unavailable');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += normalizeSseNewlines(decoder.decode(value, { stream: true }));
    buffer = drainSseBuffer(buffer, onEvent);
  }
  buffer += normalizeSseNewlines(decoder.decode());
  drainSseBuffer(`${buffer}\n\n`, onEvent);
}

function normalizeSseNewlines(value: string): string {
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

function drainSseBuffer(
  buffer: string,
  onEvent: (event: string, data: unknown) => void
): string {
  let nextBuffer = buffer;
  let boundary = nextBuffer.indexOf('\n\n');

  while (boundary !== -1) {
    const rawEvent = nextBuffer.slice(0, boundary);
    nextBuffer = nextBuffer.slice(boundary + 2);
    dispatchSseEvent(rawEvent, onEvent);
    boundary = nextBuffer.indexOf('\n\n');
  }

  return nextBuffer;
}

function dispatchSseEvent(
  rawEvent: string,
  onEvent: (event: string, data: unknown) => void
) {
  const lines = rawEvent.split('\n');
  const eventLine = lines.find((line) => line.startsWith('event:'));
  const dataLines = lines
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice('data:'.length).trimStart());

  if (!eventLine) return;

  const event = eventLine.slice('event:'.length).trim();
  const rawData = dataLines.join('\n');
  let data: unknown = rawData;
  if (rawData) {
    try {
      data = JSON.parse(rawData);
    } catch {
      data = rawData;
    }
  }
  onEvent(event, data);
}
