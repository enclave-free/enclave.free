import { describe, expect, it, vi } from 'vitest';
import {
  buildAdminDocumentContextSection,
  fetchBoundedAdminDocumentContext,
  shouldIncludeAdminDocumentContext,
} from './adminDocumentContext';

describe('shouldIncludeAdminDocumentContext', () => {
  it('includes document context for requests about uploaded guides', () => {
    expect(
      shouldIncludeAdminDocumentContext(
        'Set up the theme from the uploaded guide.'
      )
    ).toBe(true);
  });

  it('excludes document context for unrelated deployment configuration requests', () => {
    expect(shouldIncludeAdminDocumentContext('Review deployment config.')).toBe(
      false
    );
  });

  it('excludes document context for document-defaults governance requests', () => {
    expect(
      shouldIncludeAdminDocumentContext('Update default document access rules')
    ).toBe(false);
  });

  it('includes document context for copy alignment requests', () => {
    expect(
      shouldIncludeAdminDocumentContext(
        'Align the instance tagline copy with our handbook.'
      )
    ).toBe(true);
  });
});

describe('buildAdminDocumentContextSection', () => {
  it('formats bounded document excerpts in a separate context section', () => {
    const result = buildAdminDocumentContextSection({
      documents: [
        {
          job_id: 'job-1',
          filename: 'brand-guide.pdf',
          preview_chunks: [{ text: 'Use blue as the primary brand color.' }],
        },
      ],
      limits: {
        max_documents: 5,
        max_chunks_per_document: 3,
        max_chars_per_chunk: 1200,
      },
    });

    expect(result.included).toBe(true);
    expect(result.context).toContain('BOUNDED DOCUMENT CONTEXT');
    expect(result.context).toContain(
      'budget: document-library (separate from scoped config context)'
    );
    expect(result.context).toContain('brand-guide.pdf');
    expect(result.context).toContain('GUARDRAIL');
    expect(result.reduced).toBe(false);
  });

  it('flags reduced document context when preview was truncated', () => {
    const result = buildAdminDocumentContextSection({
      documents: [
        {
          job_id: 'job-1',
          filename: 'handbook.pdf',
          preview_chunks: [{ text: 'Chapter 1 excerpt' }],
          preview_truncated: true,
        },
      ],
    });

    expect(result.reduced).toBe(true);
    expect(result.context).toContain('DOCUMENT CONTEXT NOTE');
  });
});

describe('fetchBoundedAdminDocumentContext', () => {
  it('does not fetch context preview for unrelated requests', async () => {
    const fetchJson = vi.fn();

    const result = await fetchBoundedAdminDocumentContext({
      query: 'Review deployment config.',
      fetchJson,
    });

    expect(fetchJson).not.toHaveBeenCalled();
    expect(result.included).toBe(false);
  });

  it('fetches context preview for relevant requests', async () => {
    const fetchJson = vi.fn(async (endpoint: string) => {
      if (endpoint === '/ingest/admin/documents/context-preview') {
        return {
          documents: [
            {
              job_id: 'job-1',
              filename: 'guide.pdf',
              preview_chunks: [{ text: 'Theme colors should stay muted.' }],
            },
          ],
          limits: {
            max_documents: 5,
            max_chunks_per_document: 3,
            max_chars_per_chunk: 1200,
          },
        };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await fetchBoundedAdminDocumentContext({
      query: 'Set up the theme from the uploaded guide.',
      fetchJson,
    });

    expect(fetchJson).toHaveBeenCalledWith(
      '/ingest/admin/documents/context-preview'
    );
    expect(result.included).toBe(true);
    expect(result.context).toContain('guide.pdf');
  });

  it('returns no document context when the preview fetch fails', async () => {
    const fetchJson = vi.fn(async (endpoint: string) => {
      if (endpoint === '/ingest/admin/documents/context-preview') {
        throw new Error('context preview unavailable');
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await fetchBoundedAdminDocumentContext({
      query: 'Set up the theme from the uploaded guide.',
      fetchJson,
    });

    expect(fetchJson).toHaveBeenCalledWith(
      '/ingest/admin/documents/context-preview'
    );
    expect(result).toEqual({ included: false, context: '', reduced: false });
  });
});
