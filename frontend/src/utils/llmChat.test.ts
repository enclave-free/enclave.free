import { beforeEach, describe, expect, it, vi } from 'vitest'
import { sendLlmChatStreamWithUnifiedTools, sendLlmChatWithUnifiedTools, sendQueryStream } from './llmChat'
import { adminFetch } from './adminApi'

vi.mock('./adminApi', () => ({
  adminFetch: vi.fn(),
}))

describe('sendLlmChatWithUnifiedTools', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ message: 'ok' })))
  })

  it('sends the conversation session id on memory-backed chat turns', async () => {
    await sendLlmChatWithUnifiedTools({
      content: 'What was the secret word?',
      tools: [],
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
    })

    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'Check my deployment config',
      tools: ['admin-config'],
    })
  })

  it('sends trusted context without the removed client-executed tools contract', async () => {
    await sendLlmChatWithUnifiedTools({
      content: 'Use this context',
      tools: ['db-query'],
      baseToolContext: 'Trusted context prepared outside tool execution',
    })

    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'Use this context',
      tools: ['db-query'],
      tool_context: 'Trusted context prepared outside tool execution',
    })
  })

  it('streams assistant message lifecycle events from the chat stream endpoint', async () => {
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: assistant_message_started\ndata: {"message_id":"msg_1","session_id":"s1"}\n\n'))
          controller.enqueue(encoder.encode('event: trace_status\ndata: {"message_id":"msg_1","status":"Using Web search"}\n\n'))
          controller.enqueue(encoder.encode('event: answer_delta\ndata: {"message_id":"msg_1","delta":"Hello"}\n\n'))
          controller.enqueue(encoder.encode('event: trace_final\ndata: {"message_id":"msg_1","trace":{"visibility":"minimal","reasoning":{"summary":"Sage answered."},"tools":[],"retrieval":[]}}\n\n'))
          controller.enqueue(encoder.encode('event: done\ndata: {"message_id":"msg_1","session_id":"s1","inference_verification":{"record_id":42}}\n\n'))
          controller.close()
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } }
    )))
    const events: Array<{ event: string; data: unknown }> = []

    await sendLlmChatStreamWithUnifiedTools({
      content: 'Hello',
      tools: [],
      onEvent: (event, data) => events.push({ event, data }),
    })

    expect(fetch).toHaveBeenCalledWith('/api/llm/chat/stream', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: expect.any(String),
    }))
    expect(events.map((event) => event.event)).toEqual([
      'assistant_message_started',
      'trace_status',
      'answer_delta',
      'trace_final',
      'done',
    ])
    expect(events[1].data).toEqual({ message_id: 'msg_1', status: 'Using Web search' })
    expect(events[2].data).toEqual({ message_id: 'msg_1', delta: 'Hello' })
  })

  it('streams admin-config as an explicit backend tool without requiring client context', async () => {
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: done\ndata: {"message_id":"msg_1"}\n\n'))
          controller.close()
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } }
    )))

    await sendLlmChatStreamWithUnifiedTools({
      content: 'Check my deployment config',
      tools: ['admin-config'],
      onEvent: vi.fn(),
    })

    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'Check my deployment config',
      tools: ['admin-config'],
    })
  })

  it('sends recent conversation history with streamed admin chat turns', async () => {
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: done\ndata: {"message_id":"msg_1"}\n\n'))
          controller.close()
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } }
    )))

    await sendLlmChatStreamWithUnifiedTools({
      content: 'your suggestions above',
      tools: ['admin-config'],
      conversationHistory: [
        { role: 'user', content: 'Change more of the copy.' },
        { role: 'assistant', content: 'I recommend updating Instance Name, Assistant Name, and Reachout Title.' },
      ],
      onEvent: vi.fn(),
    })

    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'your suggestions above',
      tools: ['admin-config'],
      conversation_history: [
        { role: 'user', content: 'Change more of the copy.' },
        { role: 'assistant', content: 'I recommend updating Instance Name, Assistant Name, and Reachout Title.' },
      ],
    })
  })

  it('streams database questions as Sage-owned tool turns without client-executing /admin/tools/execute', async () => {
    vi.mocked(adminFetch).mockResolvedValue(Response.json({
      success: true,
      data: {
        sql: 'SELECT encrypted_value, ephemeral_pubkey FROM settings',
        columns: ['encrypted_value', 'ephemeral_pubkey'],
        rows: [{ encrypted_value: 'ciphertext', ephemeral_pubkey: 'pubkey' }],
        row_count: 1,
      },
    }))
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: done\ndata: {"message_id":"msg_1"}\n\n'))
          controller.close()
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } }
    )))

    await sendLlmChatStreamWithUnifiedTools({
      content: 'What is in settings?',
      tools: ['db-query'],
      onEvent: vi.fn(),
    })

    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(adminFetch).not.toHaveBeenCalled()
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'What is in settings?',
      tools: ['db-query'],
    })
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
          controller.enqueue(encoder.encode('event: trace_status\ndata: {"message_id":"rag_1","status":"Searching documents"}\n\n'))
          controller.enqueue(encoder.encode('event: answer_delta\ndata: {"message_id":"rag_1","delta":"Document answer"}\n\n'))
          controller.enqueue(encoder.encode('event: done\ndata: {"message_id":"rag_1","session_id":"s1","search_term":"housing advocate","inference_verification":{"record_id":42}}\n\n'))
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
      { event: 'trace_status', data: { message_id: 'rag_1', status: 'Searching documents' } },
      { event: 'answer_delta', data: { message_id: 'rag_1', delta: 'Document answer' } },
      { event: 'done', data: { message_id: 'rag_1', session_id: 's1', search_term: 'housing advocate', inference_verification: { record_id: 42 } } },
    ])
  })

  it('sends selected documents as Required Context for query stream turns', async () => {
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: done\ndata: {"message_id":"rag_1"}\n\n'))
          controller.close()
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } }
    )))

    await sendQueryStream({
      question: 'Answer from the selected policy',
      tools: [],
      jobIds: ['selected-policy', 'selected-handbook'],
      topK: 4,
      onEvent: vi.fn(),
    })

    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      question: 'Answer from the selected policy',
      top_k: 4,
      tools: [],
      job_ids: ['selected-policy', 'selected-handbook'],
    })
  })
})
