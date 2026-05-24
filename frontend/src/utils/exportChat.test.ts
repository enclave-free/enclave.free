import { afterEach, describe, expect, it, vi } from 'vitest';
import { generateExport } from './exportChat';
import type { Message } from '../components/chat/ChatMessage';

type TestMessage = Message & {
  user_memory?: Array<{
    kind: string;
    content: string;
    importance: number;
  }>;
  userMemory?: string;
};

const translations = {
  defaultTitle: 'Conversation Export',
  roleUser: 'User',
  roleAssistant: 'Assistant',
  footer: 'Exported from {{instanceName}}',
  exportedOn: 'Exported on {{timestamp}}',
  copiedExportNotice:
    'This export is outside Active Storage Lifecycle after download.',
};

describe('generateExport', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('exports conversation messages without User Memory records', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-10T12:00:00Z'));

    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'user',
        content: 'Can you help me plan this?',
        user_memory: [
          {
            kind: 'preference',
            content: 'Prefers concise answers.',
            importance: 8,
          },
        ],
      },
      {
        id: 'm2',
        role: 'assistant',
        content: 'Yes. Let us make a short plan.',
        userMemory: 'Prefers high detail answers.',
      },
    ];

    const exported = generateExport({
      messages,
      format: 'md',
      translations,
    });

    expect(exported).toContain('Can you help me plan this?');
    expect(exported).toContain('Yes. Let us make a short plan.');
    expect(exported).not.toContain('USER MEMORY');
    expect(exported).not.toContain('user_memory');
    expect(exported).not.toContain('userMemory');
    expect(exported).not.toContain('Prefers concise answers.');
    expect(exported).not.toContain('Prefers high detail answers.');
    expect(exported).not.toContain('importance');
    expect(exported).toContain('Source: Enclave Conversation Export');
    expect(exported).toContain('outside Active Storage Lifecycle');

    const exportedTxt = generateExport({
      messages,
      format: 'txt',
      translations,
    });

    expect(exportedTxt).toContain('Can you help me plan this?');
    expect(exportedTxt).toContain('Yes. Let us make a short plan.');
    expect(exportedTxt).not.toContain('USER MEMORY');
    expect(exportedTxt).not.toContain('user_memory');
    expect(exportedTxt).not.toContain('userMemory');
    expect(exportedTxt).not.toContain('Prefers concise answers.');
    expect(exportedTxt).not.toContain('Prefers high detail answers.');
    expect(exportedTxt).not.toContain('importance');
    expect(exportedTxt).toContain('Source: Enclave Conversation Export');
    expect(exportedTxt).toContain('outside Active Storage Lifecycle');
  });

  it('exports viewer-visible Conversation Trace metadata', () => {
    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'assistant',
        content: 'Here is the answer.',
        trace: {
          visibility: 'summary',
          reasoning: {
            summary: 'Sage used Web search before answering.',
          },
          tools: [
            {
              id: 'web-search',
              name: 'Web search',
              status: 'success',
              execution: 'server',
              output_summary: 'Found 3 relevant results.',
              warnings: [],
              metadata: {},
            },
          ],
          retrieval: [],
          suppressed: false,
        },
      },
    ];

    const exported = generateExport({
      messages,
      format: 'md',
      translations,
    });

    expect(exported).toContain('Conversation Trace');
    expect(exported).toContain('Sage used Web search before answering\\.');
    expect(exported).toContain('Web search');
    expect(exported).toContain('Found 3 relevant results\\.');
  });

  it('exports viewer-visible Conversation Activity Steps with settled trace metadata', () => {
    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'assistant',
        content: 'Here is the answer.',
        trace: {
          visibility: 'detailed',
          reasoning: {
            summary: 'Sage checked configuration before answering.',
          },
          tools: [],
          retrieval: [],
          activity_steps: [
            {
              id: 'tool-admin-config',
              kind: 'tool',
              title: 'Admin Config',
              status: 'succeeded',
              summary: 'Tool completed.',
              warnings: [],
            },
          ],
          suppressed: false,
        },
      },
    ];

    const exported = generateExport({
      messages,
      format: 'md',
      translations,
    });

    expect(exported).toContain('Conversation Activity');
    expect(exported).toContain('Admin Config');
    expect(exported).toContain('Tool completed\\.');
  });

  it('exports completed-turn Conversation Activity Steps even when final trace is unavailable', () => {
    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'assistant',
        content: 'Here is the answer.',
        activitySteps: [
          {
            id: 'tool-web-search',
            kind: 'tool',
            title: 'Web Search',
            status: 'succeeded',
            summary: 'Tool completed.',
            warnings: [],
          },
        ],
      },
    ];

    const exportedMarkdown = generateExport({
      messages,
      format: 'md',
      translations,
    });
    const exportedText = generateExport({
      messages,
      format: 'txt',
      translations,
    });

    expect(exportedMarkdown).toContain('Conversation Activity');
    expect(exportedMarkdown).toContain('Web Search');
    expect(exportedMarkdown).toContain('Tool completed\\.');
    expect(exportedText).toContain('Conversation Activity');
    expect(exportedText).toContain('Web Search');
    expect(exportedText).toContain('Tool completed.');
  });

  it('exports submitted-turn Conversation Control Snapshots without browser state details', () => {
    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'user',
        content: 'Use the handbook.',
        controlSnapshot: {
          selectedTools: ['web-search'],
          selectedDocuments: ['doc-1'],
        },
      },
    ];

    const exportedMarkdown = generateExport({
      messages,
      format: 'md',
      translations,
    });
    const exportedText = generateExport({
      messages,
      format: 'txt',
      translations,
    });

    expect(exportedMarkdown).toContain('Conversation Controls');
    expect(exportedMarkdown).toContain('Tools: web\\-search');
    expect(exportedMarkdown).toContain('Documents: doc\\-1');
    expect(exportedMarkdown).not.toContain('localStorage');

    expect(exportedText).toContain('Conversation Controls');
    expect(exportedText).toContain('Tools: web-search');
    expect(exportedText).toContain('Documents: doc-1');
    expect(exportedText).not.toContain('localStorage');
  });

  it('normalizes instance name metadata to one safe line', () => {
    const exported = generateExport({
      messages: [],
      format: 'md',
      translations,
      instanceName: '  Enclave\nInjected\r\u0000Name  ',
    });

    expect(exported).toContain(
      'Source: Enclave Injected Name Conversation Export'
    );
    expect(exported).toContain('Exported from Enclave Injected Name');
    expect(exported).not.toContain('Source: Enclave\nInjected');
  });

  it('escapes markdown metacharacters in markdown instance name metadata', () => {
    const exported = generateExport({
      messages: [],
      format: 'md',
      translations,
      instanceName: '[Enclave](https://example.com)',
    });

    expect(exported).toContain(
      'Source: \\[Enclave\\]\\(https://example\\.com\\) Conversation Export'
    );
    expect(exported).toContain(
      'Exported from \\[Enclave\\]\\(https://example\\.com\\)'
    );
    expect(exported).not.toContain('Source: [Enclave](https://example.com)');
  });

  it('exports only compact badges for minimal Conversation Trace metadata', () => {
    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'assistant',
        content: 'Here is the answer.',
        trace: {
          visibility: 'minimal',
          reasoning: {
            summary: 'Sage used Web search before answering.',
          },
          tools: [
            {
              id: 'web-search',
              name: 'Web search',
              status: 'success',
              execution: 'server',
              output_summary: 'Found 3 relevant results.',
              warnings: [],
              metadata: {},
            },
          ],
          retrieval: [
            {
              source_type: 'document',
              title: 'Tenant Rights Guide',
              summary: 'Matched eviction timeline section.',
            },
          ],
          suppressed: false,
        },
      },
    ];

    const exported = generateExport({
      messages,
      format: 'md',
      translations,
    });

    expect(exported).toContain('Conversation Trace');
    expect(exported).toContain('Web search');
    expect(exported).toContain('Tenant Rights Guide');
    expect(exported).not.toContain('Sage used Web search before answering.');
    expect(exported).not.toContain('Found 3 relevant results.');
    expect(exported).not.toContain('Matched eviction timeline section.');
  });

  it('escapes markdown metacharacters in exported trace and control metadata', () => {
    const exported = generateExport({
      messages: [
        {
          id: 'm1',
          role: 'user',
          content: 'Use selected context.',
          controlSnapshot: {
            selectedTools: ['[web](https://example.com)'],
            selectedDocuments: ['doc-*'],
          },
        },
        {
          id: 'm2',
          role: 'assistant',
          content: 'Done.',
          trace: {
            visibility: 'summary',
            reasoning: { summary: 'Used [reason](https://example.com).' },
            tools: [
              {
                id: 'tool-1',
                name: '[Tool](https://example.com)',
                status: 'success',
                output_summary: 'Saw *markdown*.',
              },
            ],
            retrieval: [
              {
                title: 'Doc *Title*',
                summary: 'Matched [section](https://example.com).',
              },
            ],
          },
        },
      ],
      format: 'md',
      translations,
    });

    expect(exported).toContain('\\[web\\]\\(https://example\\.com\\)');
    expect(exported).toContain('doc\\-\\*');
    expect(exported).toContain('\\[Tool\\]\\(https://example\\.com\\)');
    expect(exported).toContain('Saw \\*markdown\\*');
    expect(exported).toContain('Doc \\*Title\\*');
    expect(exported).toContain(
      'Matched \\[section\\]\\(https://example\\.com\\)'
    );
  });
});
