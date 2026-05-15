import { beforeEach, describe, expect, it, vi } from 'vitest'
import { sendLlmChatStreamWithUnifiedTools, sendLlmChatWithUnifiedTools, sendQueryStream } from './llmChat'

vi.mock('./adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => false),
}))

vi.mock('./encryption', () => ({
  decryptField: vi.fn(),
  hasNip04Support: vi.fn(() => false),
}))

describe('sendLlmChatWithUnifiedTools', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ message: 'ok' })))
  })

  it('sends the conversation session id on memory-backed chat turns', async () => {
    await sendLlmChatWithUnifiedTools({
      content: 'What was the secret word?',
      tools: [],
      t: (key) => key,
      sessionId: 'session-123',
    })

    expect(fetch).toHaveBeenCalledWith('/api/llm/chat', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: expect.any(String),
    }))
    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'What was the secret word?',
      tools: [],
      session_id: 'session-123',
    })
  })

  it('omits session_id when no conversation session id is provided', async () => {
    await sendLlmChatWithUnifiedTools({
      content: 'Start fresh',
      tools: [],
      t: (key) => key,
    })

    expect(fetch).toHaveBeenCalledWith('/api/llm/chat', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: expect.any(String),
    }))
    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).not.toHaveProperty('session_id')
  })

  it('sends admin-config as a backend tool instead of requiring client tool context', async () => {
    await sendLlmChatWithUnifiedTools({
      content: 'Check my deployment config',
      tools: ['admin-config'],
      t: (key) => key,
    })

    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'Check my deployment config',
      tools: ['admin-config'],
    })
  })

  it('streams assistant message lifecycle events from the chat stream endpoint', async () => {
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: assistant_message_started\ndata: {"message_id":"msg_1","session_id":"s1"}\n\n'))
          controller.enqueue(encoder.encode('event: answer_delta\ndata: {"message_id":"msg_1","delta":"Hello"}\n\n'))
          controller.enqueue(encoder.encode('event: trace_final\ndata: {"message_id":"msg_1","trace":{"visibility":"minimal","reasoning":{"summary":"Sage answered."},"tools":[],"retrieval":[]}}\n\n'))
          controller.enqueue(encoder.encode('event: done\ndata: {"message_id":"msg_1","session_id":"s1"}\n\n'))
          controller.close()
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } }
    )))
    const events: Array<{ event: string; data: unknown }> = []

    await sendLlmChatStreamWithUnifiedTools({
      content: 'Hello',
      tools: [],
      t: (key) => key,
      onEvent: (event, data) => events.push({ event, data }),
    })

    expect(fetch).toHaveBeenCalledWith('/api/llm/chat/stream', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: expect.any(String),
    }))
    expect(events.map((event) => event.event)).toEqual([
      'assistant_message_started',
      'answer_delta',
      'trace_final',
      'done',
    ])
    expect(events[1].data).toEqual({ message_id: 'msg_1', delta: 'Hello' })
  })

  it('parses stream events split across chunks with CRLF boundaries', async () => {
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: answer_delta\r\n'))
          controller.enqueue(encoder.encode('data: {"message_id":"msg_1","delta":"Hel'))
          controller.enqueue(encoder.encode('lo"}\r\n\r\n'))
          controller.close()
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } }
    )))
    const events: Array<{ event: string; data: unknown }> = []

    await sendLlmChatStreamWithUnifiedTools({
      content: 'Hello',
      tools: [],
      t: (key) => key,
      onEvent: (event, data) => events.push({ event, data }),
    })

    expect(events).toEqual([
      { event: 'answer_delta', data: { message_id: 'msg_1', delta: 'Hello' } },
    ])
  })

  it('streams RAG answers from the query stream endpoint', async () => {
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: assistant_message_started\ndata: {"message_id":"rag_1","session_id":"s1"}\n\n'))
          controller.enqueue(encoder.encode('event: answer_delta\ndata: {"message_id":"rag_1","delta":"Document answer"}\n\n'))
          controller.enqueue(encoder.encode('event: done\ndata: {"message_id":"rag_1","session_id":"s1","search_term":"housing advocate"}\n\n'))
          controller.close()
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } }
    )))
    const events: Array<{ event: string; data: unknown }> = []

    await sendQueryStream({
      question: 'What help is available?',
      tools: ['web-search'],
      jobIds: ['job-1'],
      sessionId: 'session-123',
      onEvent: (event, data) => events.push({ event, data }),
    })

    expect(fetch).toHaveBeenCalledWith('/api/query/stream', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: expect.any(String),
    }))
    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      question: 'What help is available?',
      top_k: 8,
      tools: ['web-search'],
      job_ids: ['job-1'],
      session_id: 'session-123',
    })
    expect(events).toEqual([
      { event: 'assistant_message_started', data: { message_id: 'rag_1', session_id: 's1' } },
      { event: 'answer_delta', data: { message_id: 'rag_1', delta: 'Document answer' } },
      { event: 'done', data: { message_id: 'rag_1', session_id: 's1', search_term: 'housing advocate' } },
    ])
  })
})
