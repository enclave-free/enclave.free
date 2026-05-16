import { API_BASE } from '../types/onboarding'

interface SendLlmChatOptions {
  content: string
  tools: string[]
  baseToolContext?: string
  sessionId?: string | null
  conversationHistory?: Array<{ role: 'user' | 'assistant'; content: string }>
}

interface SendLlmChatStreamOptions extends SendLlmChatOptions {
  onEvent: (event: string, data: unknown) => void
}

interface SendQueryStreamOptions {
  question: string
  tools: string[]
  jobIds: string[]
  onEvent: (event: string, data: unknown) => void
  sessionId?: string | null
  topK?: number
}

async function buildUnifiedChatBody({
  content,
  tools,
  baseToolContext,
  sessionId,
  conversationHistory,
}: SendLlmChatOptions): Promise<Record<string, unknown>> {
  const toolContextParts: string[] = []
  if (baseToolContext && baseToolContext.trim()) {
    toolContextParts.push(baseToolContext.trim())
  }

  const body: Record<string, unknown> = {
    message: content,
    tools,
  }
  if (sessionId) {
    body.session_id = sessionId
  }
  const recentHistory = (conversationHistory || [])
    .filter((message) => (
      (message.role === 'user' || message.role === 'assistant') &&
      typeof message.content === 'string' &&
      message.content.trim()
    ))
    .slice(-8)
    .map((message) => ({
      role: message.role,
      content: message.content.slice(0, 2000),
    }))
  if (recentHistory.length > 0) {
    body.conversation_history = recentHistory
  }

  if (toolContextParts.length > 0) {
    body.tool_context = toolContextParts.join('\n\n')
  }

  return body
}

export async function sendLlmChatWithUnifiedTools(options: SendLlmChatOptions): Promise<Response> {
  const body = await buildUnifiedChatBody(options)

  return fetch(`${API_BASE}/llm/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(body),
  })
}

export async function sendLlmChatStreamWithUnifiedTools({
  onEvent,
  ...options
}: SendLlmChatStreamOptions): Promise<void> {
  const body = await buildUnifiedChatBody(options)
  const response = await fetch(`${API_BASE}/llm/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  await readSseResponse(response, onEvent)
}

export async function sendQueryStream({
  question,
  tools,
  jobIds,
  onEvent,
  sessionId,
  topK = 8,
}: SendQueryStreamOptions): Promise<void> {
  const body: Record<string, unknown> = {
    question,
    top_k: topK,
    tools,
    job_ids: jobIds,
  }
  if (sessionId) {
    body.session_id = sessionId
  }

  const response = await fetch(`${API_BASE}/query/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  await readSseResponse(response, onEvent)
}

async function readSseResponse(response: Response, onEvent: (event: string, data: unknown) => void): Promise<void> {
  if (!response.body) {
    throw new Error('Streaming response body is unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += normalizeSseNewlines(decoder.decode(value, { stream: true }))
    buffer = drainSseBuffer(buffer, onEvent)
  }
  buffer += normalizeSseNewlines(decoder.decode())
  drainSseBuffer(`${buffer}\n\n`, onEvent)
}

function normalizeSseNewlines(value: string): string {
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
}

function drainSseBuffer(buffer: string, onEvent: (event: string, data: unknown) => void): string {
  let nextBuffer = buffer
  let boundary = nextBuffer.indexOf('\n\n')

  while (boundary !== -1) {
    const rawEvent = nextBuffer.slice(0, boundary)
    nextBuffer = nextBuffer.slice(boundary + 2)
    dispatchSseEvent(rawEvent, onEvent)
    boundary = nextBuffer.indexOf('\n\n')
  }

  return nextBuffer
}

function dispatchSseEvent(rawEvent: string, onEvent: (event: string, data: unknown) => void) {
  const lines = rawEvent.split('\n')
  const eventLine = lines.find((line) => line.startsWith('event:'))
  const dataLines = lines
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice('data:'.length).trimStart())

  if (!eventLine) return

  const event = eventLine.slice('event:'.length).trim()
  const rawData = dataLines.join('\n')
  let data: unknown = rawData
  if (rawData) {
    try {
      data = JSON.parse(rawData)
    } catch {
      data = rawData
    }
  }
  onEvent(event, data)
}
