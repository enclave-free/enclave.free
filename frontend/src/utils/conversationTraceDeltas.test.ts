import { describe, expect, it } from 'vitest';
import { mergeTraceDeltas } from './conversationTraceDeltas';

describe('conversation trace delta merging', () => {
  it('keeps both Tool attempts and lifecycle order when streaming updates arrive', () => {
    const callId = 'call-1';
    const deltas = mergeTraceDeltas(
      [],
      [
        {
          id: `${callId}-attempted-1`,
          kind: 'tool_call',
          title: 'Curated Resources',
          content: 'Curated Resources call attempted.',
          tool_name: 'find_resources',
          status: 'running',
          metadata: { phase: 'attempted', call_id: callId, attempt: 1 },
        },
        {
          id: `${callId}-retry-1`,
          kind: 'tool_retry',
          title: 'Curated Resources',
          content: 'Retrying Curated Resources after attempt 1.',
          tool_name: 'find_resources',
          status: 'running',
          metadata: { phase: 'retry', call_id: callId, attempt: 1 },
        },
        {
          id: `${callId}-attempted-2`,
          kind: 'tool_call',
          title: 'Curated Resources',
          content: 'Curated Resources call attempted.',
          tool_name: 'find_resources',
          status: 'running',
          metadata: { phase: 'attempted', call_id: callId, attempt: 2 },
        },
        {
          id: `${callId}-terminal`,
          kind: 'tool_result',
          title: 'Curated Resources',
          content: 'Tool timed out.',
          tool_name: 'find_resources',
          status: 'timed_out',
          metadata: { phase: 'terminal', call_id: callId, attempt: 2 },
        },
      ]
    );

    expect(deltas.map((delta) => delta.id)).toEqual([
      `${callId}-attempted-1`,
      `${callId}-retry-1`,
      `${callId}-attempted-2`,
      `${callId}-terminal`,
    ]);
    expect(deltas.filter((delta) => delta.kind === 'tool_call')).toHaveLength(
      2
    );
    expect(deltas[0].metadata?.call_id).toBe(callId);
    expect(deltas[2].metadata?.call_id).toBe(callId);
  });
});
