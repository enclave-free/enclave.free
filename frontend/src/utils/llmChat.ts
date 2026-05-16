import { API_BASE } from '../types/onboarding'
import { adminFetch, isAdminAuthenticated } from './adminApi'
import { decryptField, hasNip04Support } from './encryption'

type DbQueryToolData = {
  sql?: string
  columns?: string[]
  rows?: Record<string, unknown>[]
  row_count?: number
  truncated?: boolean
}

type TranslateFn = (key: string, options?: Record<string, unknown>) => string

const formatDbCell = (value: unknown) => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const decryptDbQueryData = async (data: DbQueryToolData) => {
  const columns = data.columns || []
  const rows = data.rows || []
  let encryptedValueCount = 0
  let decryptedCount = 0

  const outputColumns = columns.reduce<string[]>((acc, col) => {
    if (col.startsWith('ephemeral_pubkey')) return acc
    if (col.startsWith('encrypted_')) {
      const fieldName = col.replace('encrypted_', '')
      if (!acc.includes(fieldName)) acc.push(fieldName)
      return acc
    }
    if (!acc.includes(col)) acc.push(col)
    return acc
  }, [])

  const decryptedRows = await Promise.all(
    rows.map(async (row) => {
      const nextRow: Record<string, unknown> = {}

      for (const col of columns) {
        if (col.startsWith('ephemeral_pubkey')) {
          continue
        }

        if (col.startsWith('encrypted_')) {
          const fieldName = col.replace('encrypted_', '')
          const ciphertext = row[col]
          if (typeof ciphertext !== 'string' || !ciphertext) {
            continue
          }
          encryptedValueCount += 1

          let ephemeral = row[col.replace('encrypted_', 'ephemeral_pubkey_')]
          if (!ephemeral && col === 'encrypted_value') {
            ephemeral = row['ephemeral_pubkey']
          }

          if (typeof ephemeral !== 'string' || !ephemeral) {
            nextRow[fieldName] = ciphertext
            continue
          }

          try {
            const decrypted = await decryptField({ ciphertext, ephemeral_pubkey: ephemeral })
            if (decrypted !== null) {
              decryptedCount += 1
            }
            nextRow[fieldName] = decrypted ?? ciphertext
          } catch {
            nextRow[fieldName] = ciphertext
          }
          continue
        }

        if (nextRow[col] === undefined) {
          nextRow[col] = row[col]
        }
      }

      return nextRow
    })
  )

  return { columns: outputColumns, rows: decryptedRows, encryptedValueCount, decryptedCount }
}

const formatDbQueryContext = (
  data: DbQueryToolData,
  columns: string[],
  rows: Record<string, unknown>[],
  t: TranslateFn
) => {
  const lines: string[] = []

  if (data.sql) {
    lines.push(t('chat.database.executedSql', { sql: data.sql }))
    lines.push('')
  }

  if (!rows.length) {
    lines.push(t('chat.database.noResults'))
    return lines.join('\n')
  }

  lines.push(t('chat.database.resultsCount', { count: rows.length }))

  if (data.truncated) {
    lines.push(t('chat.database.resultsTruncated'))
  }

  lines.push('')
  lines.push(columns.join(' | '))
  lines.push('-'.repeat(columns.join(' | ').length))

  for (const row of rows) {
    const values = columns.map((col) => formatDbCell(row[col]))
    lines.push(values.join(' | '))
  }

  return lines.join('\n')
}

interface SendLlmChatOptions {
  content: string
  tools: string[]
  t: TranslateFn
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
  t,
  baseToolContext,
  sessionId,
  conversationHistory,
}: SendLlmChatOptions): Promise<Record<string, unknown>> {
  const toolContextParts: string[] = []
  if (baseToolContext && baseToolContext.trim()) {
    toolContextParts.push(baseToolContext.trim())
  }

  let clientExecutedTools: string[] = []
  const wantsDbQuery = tools.includes('db-query')
  const canDecryptDbQuery = wantsDbQuery && isAdminAuthenticated() && hasNip04Support()

  if (canDecryptDbQuery) {
    try {
      const toolResponse = await adminFetch('/admin/tools/execute', {
        method: 'POST',
        body: JSON.stringify({ tool_id: 'db-query', query: content }),
      })

      if (toolResponse.ok) {
        const toolPayload = await toolResponse.json()
        if (toolPayload?.success && toolPayload?.data) {
          const decrypted = await decryptDbQueryData(toolPayload.data as DbQueryToolData)
          const hasEncryptedValues = decrypted.encryptedValueCount > 0

          if (!hasEncryptedValues || decrypted.decryptedCount > 0) {
            const dbContext = formatDbQueryContext(
              toolPayload.data as DbQueryToolData,
              decrypted.columns,
              decrypted.rows,
              t
            )
            if (dbContext.trim()) {
              toolContextParts.push(dbContext)
              clientExecutedTools = ['db-query']
            }
          }
        }
      }
    } catch (e) {
      console.warn('Falling back to server-side db-query tool execution:', e)
    }
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
    // Send explicit client-executed tools list. Empty array means
    // "tool_context exists, but no tools were pre-executed".
    body.client_executed_tools = clientExecutedTools
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
