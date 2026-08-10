import { memo, useEffect, useId, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import {
  oneDark,
  oneLight,
} from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { CSSProperties, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  Database,
  FileSearch,
  Info,
  Loader2,
  Pencil,
  RotateCcw,
  Search,
  Sparkles,
  Square,
  Wrench,
} from 'lucide-react';
import { useTheme } from '../../theme';
import { useInstanceConfig } from '../../context/InstanceConfigContext';
import { DynamicIcon } from '../shared/DynamicIcon';
import { Button } from '../ui';
import type {
  ConversationMessageAction,
  ConversationMessageActionId,
} from './ConversationMessageActions';

export interface ConversationTrace {
  visibility: 'off' | 'minimal' | 'summary' | 'detailed';
  reasoning?: {
    summary?: string;
  };
  tools?: Array<{
    id: string;
    name: string;
    status?: string;
    execution?: string;
    input_summary?: string | null;
    output_summary?: string | null;
    warnings?: string[];
    metadata?: Record<string, unknown>;
  }>;
  retrieval?: Array<{
    source_type?: string;
    title?: string | null;
    summary?: string | null;
    score?: number | null;
  }>;
  trace_deltas?: ConversationTraceDelta[];
  activity_steps?: ConversationActivityStep[];
  suppressed?: boolean;
}

export interface ConversationTraceDelta {
  id: string;
  kind:
    | 'reasoning'
    | 'model_step'
    | 'tool_call'
    | 'tool_result'
    | 'tool_selection_observation'
    | 'retry'
    | 'tool_retry'
    | 'timeout'
    | 'correction'
    | 'retrieval'
    | 'timing';
  title?: string;
  content?: string;
  tool_name?: string;
  status?: 'running' | 'succeeded' | 'failed' | 'guarded' | string;
  metadata?: Record<string, unknown>;
  created_at?: string;
}

export interface ConversationActivityStep {
  id: string;
  kind: string;
  title: string;
  status: string;
  summary?: string;
  warnings?: string[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: Date;
  trace?: ConversationTrace | null;
  traceStatus?: string | null;
  activitySteps?: ConversationActivityStep[];
  traceDeltas?: ConversationTraceDelta[];
  controlSnapshot?: {
    selectedTools: string[];
    selectedDocuments: string[];
  };
  actions?: ConversationMessageAction[];
}

interface ChatMessageProps {
  message: Message;
  onAction?: (actionId: ConversationMessageActionId, message: Message) => void;
}

function UserIcon({ iconName }: { iconName: string }) {
  return (
    <div className="w-7 h-7 rounded-full bg-accent/10 flex items-center justify-center shrink-0 ring-1 ring-accent/20">
      <DynamicIcon name={iconName} size={16} className="text-accent" />
    </div>
  );
}

function AssistantIcon({ iconName }: { iconName: string }) {
  return (
    <div className="w-7 h-7 rounded-full border border-border bg-surface-raised flex items-center justify-center shrink-0">
      <DynamicIcon name={iconName} size={16} className="text-accent" />
    </div>
  );
}

async function copyTextToClipboard(text: string): Promise<boolean> {
  if (
    typeof navigator === 'undefined' ||
    !navigator.clipboard ||
    typeof navigator.clipboard.writeText !== 'function'
  ) {
    console.error('Clipboard API is unavailable.');
    return false;
  }

  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    console.error('Failed to copy text to clipboard.', error);
    return false;
  }
}

interface CodeBlockProps {
  language: string | null;
  children: string;
  resolvedTheme: 'light' | 'dark';
}

function CodeBlock({ language, children, resolvedTheme }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const { t } = useTranslation();

  const handleCopy = async () => {
    const copiedToClipboard = await copyTextToClipboard(children);
    if (!copiedToClipboard) return;
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const codeStyle = resolvedTheme === 'dark' ? oneDark : oneLight;

  return (
    <div className="my-4 rounded-xl overflow-hidden border border-border shadow-md group">
      <div className="flex items-center justify-between px-4 py-2.5 bg-surface-raised border-b border-border">
        <div className="flex items-center gap-2">
          <span className="label">{language || 'code'}</span>
        </div>
        <Button
          onClick={handleCopy}
          variant="ghost"
          size="sm"
          leadingIcon={
            copied ? (
              <Check className="h-3.5 w-3.5 text-success" aria-hidden="true" />
            ) : (
              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
            )
          }
          className="text-xs"
          aria-label={copied ? t('chat.code.copied') : t('chat.code.copyCode')}
        >
          {copied ? t('chat.code.copied') : t('chat.code.copy')}
        </Button>
      </div>
      <SyntaxHighlighter
        style={codeStyle as { [key: string]: CSSProperties }}
        language={language || 'text'}
        PreTag="div"
        showLineNumbers={false}
        customStyle={{
          margin: 0,
          padding: '1rem 1.25rem',
          fontSize: '0.8125rem',
          lineHeight: '1.7',
        }}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
}

function ConversationTracePanel({
  trace,
  activitySteps = [],
  traceDeltas = [],
  liveStatus,
  isStreaming = false,
}: {
  trace?: ConversationTrace | null;
  activitySteps?: ConversationActivityStep[];
  traceDeltas?: ConversationTraceDelta[];
  liveStatus?: string | null;
  isStreaming?: boolean;
}) {
  const [activityOpen, setActivityOpen] = useState(true);
  const [optionalDetailsOpen, setOptionalDetailsOpen] = useState(false);
  const activityBodyId = useId();
  const optionalDetailsBaseId = useId();
  const visibility = trace?.visibility;
  const tools = trace?.tools ?? [];
  const retrieval = trace?.retrieval ?? [];
  const summary = trace?.reasoning?.summary;
  const combinedActivitySteps =
    activitySteps.length > 0 ? activitySteps : (trace?.activity_steps ?? []);
  const reasoningDeltas = traceDeltas.filter(
    (delta) => delta.kind === 'reasoning'
  );
  const operationalTraceDeltas = traceDeltas.filter(
    (delta) => delta.kind !== 'reasoning'
  );
  const hasActivity = combinedActivitySteps.length > 0;
  const hasTraceDeltas = traceDeltas.length > 0;
  const hasTraceChips = tools.length > 0 || retrieval.length > 0;
  const hasTraceDetail = Boolean(summary) || hasTraceChips;
  const isLive = Boolean(liveStatus);
  const reasoningSummaryId = summary
    ? `${optionalDetailsBaseId}-reasoning`
    : undefined;
  const toolOptionalDetailIds = tools.map((tool, index) =>
    tool.input_summary || tool.output_summary
      ? `${optionalDetailsBaseId}-tool-${index}`
      : undefined
  );
  const retrievalOptionalDetailIds = retrieval.map((item, index) =>
    item.summary ? `${optionalDetailsBaseId}-retrieval-${index}` : undefined
  );
  const optionalDetailIds = [
    reasoningSummaryId,
    ...toolOptionalDetailIds,
    ...retrievalOptionalDetailIds,
  ].filter((id): id is string => Boolean(id));
  const hasExpandableDetails = optionalDetailIds.length > 0;

  if (visibility === 'off' && !isLive && !hasActivity && !hasTraceDeltas)
    return null;
  if (!isLive && !hasActivity && !hasTraceDeltas && !hasTraceDetail)
    return null;

  if (visibility === 'minimal' && !isLive && !hasActivity && !hasTraceDeltas) {
    if (!hasTraceChips) return null;

    return (
      <div
        className="mt-3 flex flex-wrap gap-2 border-t border-border/70 pt-3 text-xs text-text-muted"
        aria-label="Activity summary"
      >
        {tools.map((tool) => (
          <div
            key={tool.id}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1"
          >
            <TraceIcon kind="tool" name={tool.name} />
            <span className="font-medium text-text">{tool.name}</span>
          </div>
        ))}
        {retrieval.map((item, index) => (
          <div
            key={`${item.title ?? item.source_type ?? 'retrieval'}-${index}`}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1"
          >
            <FileSearch
              className="h-3.5 w-3.5 text-accent"
              aria-hidden="true"
            />
            <span className="font-medium text-text">
              {item.title || item.source_type || 'Retrieved source'}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <section
      className="mt-3 overflow-hidden rounded-lg border border-border/80 bg-surface text-xs text-text-muted"
      aria-label="Activity"
    >
      <button
        type="button"
        onClick={() => setActivityOpen((open) => !open)}
        aria-expanded={activityOpen}
        aria-controls={activityBodyId}
        aria-label={activityOpen ? 'Hide Activity' : 'Show Activity'}
        className={`flex w-full items-center justify-between gap-3 bg-surface-raised px-3 py-2 text-left outline-none transition hover:bg-surface-overlay focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/40 ${
          activityOpen ? 'border-b border-border/70' : ''
        }`}
      >
        <div className="flex min-w-0 items-center gap-2">
          {isLive ? (
            <Loader2
              className="h-3.5 w-3.5 shrink-0 animate-spin text-accent"
              aria-hidden="true"
            />
          ) : (
            <Info
              className="h-3.5 w-3.5 shrink-0 text-accent"
              aria-hidden="true"
            />
          )}
          <span className="font-medium text-text">Activity</span>
        </div>
        <div className="flex min-w-0 items-center gap-2">
          {liveStatus && (
            <span className="truncate text-right text-[11px] text-text-secondary">
              {liveStatus}
            </span>
          )}
          <ChevronDown
            className={`h-3.5 w-3.5 shrink-0 text-text-muted transition-transform ${
              activityOpen ? 'rotate-180' : ''
            }`}
            aria-hidden="true"
          />
        </div>
      </button>

      <div
        id={activityBodyId}
        role="region"
        aria-label="Activity details"
        className="space-y-3 px-3 py-3"
        hidden={!activityOpen}
      >
        {hasExpandableDetails && (
          <button
            type="button"
            onClick={() => setOptionalDetailsOpen((open) => !open)}
            aria-expanded={optionalDetailsOpen}
            aria-controls={optionalDetailIds.join(' ')}
            className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-[11px] font-medium text-text-secondary transition hover:bg-surface-overlay hover:text-text"
          >
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform ${optionalDetailsOpen ? 'rotate-180' : ''}`}
              aria-hidden="true"
            />
            {optionalDetailsOpen
              ? 'Hide optional details'
              : 'Show optional details'}
          </button>
        )}
        {summary && reasoningSummaryId && (
          <div
            id={reasoningSummaryId}
            role="region"
            aria-label="Reasoning summary"
            hidden={!optionalDetailsOpen}
          >
            <p className="leading-relaxed text-text-secondary">{summary}</p>
          </div>
        )}
        {hasActivity && (
          <div className="space-y-2" aria-label="Activity timeline">
            {combinedActivitySteps.map((step) => (
              <ActivityStepRow key={step.id} step={step} />
            ))}
          </div>
        )}
        {reasoningDeltas.length > 0 && (
          <ReasoningDisclosure
            deltas={reasoningDeltas}
            isLive={isStreaming && !trace}
          />
        )}
        {operationalTraceDeltas.length > 0 && (
          <TraceRows label="Trace">
            {operationalTraceDeltas.map((delta) => (
              <TraceDeltaRow key={delta.id} delta={delta} />
            ))}
          </TraceRows>
        )}
        {tools.length > 0 && (
          <TraceRows label="Tool calls">
            {tools.map((tool, index) => (
              <ToolTraceRow
                key={`${tool.id}-${tool.input_summary ?? ''}-${index}`}
                tool={tool}
                optionalDetailsOpen={optionalDetailsOpen}
                optionalDetailsId={toolOptionalDetailIds[index]}
              />
            ))}
          </TraceRows>
        )}
        {retrieval.length > 0 && (
          <TraceRows label="Retrieval">
            {retrieval.map((item, index) => (
              <RetrievalTraceRow
                key={`${item.title ?? item.source_type ?? 'retrieval'}-${index}`}
                item={item}
                optionalDetailsOpen={optionalDetailsOpen}
                optionalDetailsId={retrievalOptionalDetailIds[index]}
              />
            ))}
          </TraceRows>
        )}
      </div>
    </section>
  );
}

function ReasoningDisclosure({
  deltas,
  isLive,
}: {
  deltas: ConversationTraceDelta[];
  isLive: boolean;
}) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const transcriptId = useId();
  const transcriptRef = useRef<HTMLDivElement>(null);
  const transcript = reasoningTranscript(deltas);
  const preview = reasoningPreview(transcript);
  const label = isLive
    ? t('chat.trace.thinking', 'Thinking')
    : t('chat.trace.reasoning', 'Reasoning');
  const toggleAction = isOpen
    ? t('chat.trace.collapse', 'Collapse')
    : t('chat.trace.expand', 'Expand');
  const transcriptLabel = t('chat.trace.transcript', '{{label}} transcript', {
    label,
  });

  useEffect(() => {
    if (!isOpen || !transcriptRef.current) return;
    transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
  }, [isOpen, transcript]);

  if (!transcript) return null;

  return (
    <div
      className={`relative isolate overflow-hidden rounded-lg ${
        isLive ? 'bg-accent/[0.035]' : 'bg-surface-raised/45'
      }`}
    >
      {isLive && (
        <div
          className="pointer-events-none absolute -inset-x-8 inset-y-0 -z-10 bg-accent/10 blur-2xl motion-safe:animate-pulse-subtle"
          aria-hidden="true"
        />
      )}
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        aria-controls={transcriptId}
        aria-label={`${toggleAction} ${transcriptLabel}`}
        className="group flex min-h-11 w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left outline-none transition-[background-color,box-shadow,scale] duration-150 ease-out hover:bg-surface-overlay/60 focus-visible:ring-2 focus-visible:ring-accent/40 active:scale-[0.96]"
      >
        <Sparkles
          className={`h-3.5 w-3.5 shrink-0 ${
            isLive
              ? 'text-accent motion-safe:animate-pulse-subtle'
              : 'text-text-muted'
          }`}
          aria-hidden="true"
        />
        <span className="shrink-0 text-[11px] font-medium text-text-secondary">
          {label}
        </span>
        {!isOpen && (
          <span
            className={`min-w-0 flex-1 truncate text-[11px] ${
              isLive
                ? 'reasoning-live-text'
                : 'text-text-muted group-hover:text-text-secondary'
            }`}
          >
            {preview}
          </span>
        )}
        <ChevronDown
          className={`ml-auto h-3.5 w-3.5 shrink-0 text-text-muted transition-transform duration-150 ease-out ${
            isOpen ? 'rotate-180' : ''
          }`}
          aria-hidden="true"
        />
      </button>
      {isOpen && (
        <div
          id={transcriptId}
          ref={transcriptRef}
          role="region"
          aria-label="Reasoning transcript"
          tabIndex={0}
          className="mx-2.5 mb-2.5 max-h-64 overflow-y-auto rounded-md bg-surface/55 px-3 py-2.5 text-[12px] leading-relaxed text-text-secondary shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--color-border)_70%,transparent)] outline-none animate-fade-in focus-visible:ring-2 focus-visible:ring-accent/35"
        >
          <p className="whitespace-pre-wrap break-words">{transcript}</p>
        </div>
      )}
    </div>
  );
}

function reasoningTranscript(deltas: ConversationTraceDelta[]) {
  return deltas
    .map((delta) => delta.content ?? '')
    .join('')
    .trim();
}

function reasoningPreview(transcript: string, maxLength = 180) {
  const compact = transcript.replace(/\s+/g, ' ').trim();
  if (compact.length <= maxLength) return compact;

  const tail = compact.slice(-maxLength);
  const firstSpace = tail.indexOf(' ');
  return `…${tail.slice(firstSpace >= 0 ? firstSpace + 1 : 0)}`;
}

function isTraceRenderable(
  trace?: ConversationTrace | null,
  liveStatus?: string | null,
  activitySteps: ConversationActivityStep[] = [],
  traceDeltas: ConversationTraceDelta[] = []
): boolean {
  const isLive = Boolean(liveStatus);
  const hasTraceDeltas = traceDeltas.length > 0;
  const hasActivity =
    activitySteps.length > 0 || (trace?.activity_steps?.length ?? 0) > 0;
  if (trace?.visibility === 'off' && !isLive && !hasActivity && !hasTraceDeltas)
    return false;
  if (isLive || hasActivity || hasTraceDeltas) return true;
  const tools = trace?.tools ?? [];
  const retrieval = trace?.retrieval ?? [];
  const summary = trace?.reasoning?.summary;
  if (trace?.visibility === 'minimal')
    return tools.length > 0 || retrieval.length > 0;
  return Boolean(summary) || tools.length > 0 || retrieval.length > 0;
}

function TraceRows({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-text-muted">
        {label}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function ActivityStepRow({ step }: { step: ConversationActivityStep }) {
  return (
    <div className="rounded-md border border-border/80 bg-surface-raised px-3 py-2">
      <div className="flex items-start gap-2">
        <TraceIcon kind={step.kind} name={step.title} status={step.status} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium text-text">{step.title}</span>
            {!isSettledSuccessStatus(step.status) && (
              <TraceStatus status={step.status} />
            )}
          </div>
          {step.summary && (
            <p className="mt-1 leading-relaxed text-text-secondary">
              {step.summary}
            </p>
          )}
          <TraceWarnings warnings={step.warnings ?? []} />
        </div>
      </div>
    </div>
  );
}

function TraceDeltaRow({ delta }: { delta: ConversationTraceDelta }) {
  const title =
    delta.title || delta.tool_name || formatTraceDeltaKind(delta.kind);

  return (
    <div className="rounded-md border border-border/80 bg-surface-raised px-3 py-2">
      <div className="flex items-start gap-2">
        <TraceIcon kind={delta.kind} name={title} status={delta.status} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium text-text">{title}</span>
            {delta.tool_name && delta.tool_name !== title && (
              <span className="text-[11px] text-text-muted">
                {delta.tool_name}
              </span>
            )}
            {delta.status && <TraceStatus status={delta.status} />}
          </div>
          {delta.content && (
            <p className="mt-1 whitespace-pre-wrap break-words leading-relaxed text-text-secondary">
              {delta.content}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function formatTraceDeltaKind(kind: string) {
  return kind
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

type ToolTrace = NonNullable<ConversationTrace['tools']>[number];
type RetrievalTrace = NonNullable<ConversationTrace['retrieval']>[number];

function ToolTraceRow({
  tool,
  optionalDetailsOpen,
  optionalDetailsId,
}: {
  tool: ToolTrace;
  optionalDetailsOpen: boolean;
  optionalDetailsId?: string;
}) {
  return (
    <div className="rounded-md border border-border/80 bg-surface-raised px-3 py-2">
      <div className="flex items-start gap-2">
        <TraceIcon kind="tool" name={tool.name} status={tool.status} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium text-text">{tool.name}</span>
            {tool.execution && (
              <span className="text-[11px] text-text-muted">
                {tool.execution}
              </span>
            )}
            {tool.status && <TraceStatus status={tool.status} />}
          </div>
          {optionalDetailsId && (
            <div
              id={optionalDetailsId}
              role="region"
              aria-label={`${tool.name} optional details`}
              hidden={!optionalDetailsOpen}
            >
              {tool.input_summary && (
                <p className="mt-1 leading-relaxed">
                  <span className="font-medium text-text-secondary">
                    Input:
                  </span>{' '}
                  {tool.input_summary}
                </p>
              )}
              {tool.output_summary && (
                <p className="mt-1 leading-relaxed">
                  <span className="font-medium text-text-secondary">
                    Output:
                  </span>{' '}
                  {tool.output_summary}
                </p>
              )}
            </div>
          )}
          <TraceWarnings warnings={tool.warnings ?? []} />
        </div>
      </div>
    </div>
  );
}

function RetrievalTraceRow({
  item,
  optionalDetailsOpen,
  optionalDetailsId,
}: {
  item: RetrievalTrace;
  optionalDetailsOpen: boolean;
  optionalDetailsId?: string;
}) {
  return (
    <div className="rounded-md border border-border/80 bg-surface-raised px-3 py-2">
      <div className="flex items-start gap-2">
        <FileSearch
          className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent"
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium text-text">
              {item.title || item.source_type || 'Retrieved source'}
            </span>
            {typeof item.score === 'number' && (
              <span className="text-[11px] text-text-muted">
                score {item.score.toFixed(2)}
              </span>
            )}
          </div>
          {item.summary && optionalDetailsId && (
            <div
              id={optionalDetailsId}
              role="region"
              aria-label={`${item.title || item.source_type || 'Retrieved source'} optional details`}
              hidden={!optionalDetailsOpen}
            >
              <p className="mt-1 leading-relaxed text-text-secondary">
                {item.summary}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TraceIcon({
  kind,
  name,
  status,
}: {
  kind: string;
  name?: string;
  status?: string;
}) {
  const normalizedName = (name ?? '').toLowerCase();
  const normalizedStatus = (status ?? '').toLowerCase();
  const className = `mt-0.5 h-3.5 w-3.5 shrink-0 ${normalizedStatus.includes('fail') || normalizedStatus.includes('error') ? 'text-danger' : 'text-accent'}`;

  if (
    normalizedStatus.includes('running') ||
    normalizedStatus.includes('prepar')
  ) {
    return (
      <Loader2 className={`${className} animate-spin`} aria-hidden="true" />
    );
  }
  if (
    normalizedStatus.includes('success') ||
    normalizedStatus.includes('complete')
  ) {
    return <CheckCircle2 className={className} aria-hidden="true" />;
  }
  if (kind === 'tool' && normalizedName.includes('database')) {
    return <Database className={className} aria-hidden="true" />;
  }
  if (kind === 'tool' && normalizedName.includes('search')) {
    return <Search className={className} aria-hidden="true" />;
  }
  if (kind === 'retrieval') {
    return <FileSearch className={className} aria-hidden="true" />;
  }
  return <Wrench className={className} aria-hidden="true" />;
}

function TraceStatus({ status }: { status: string }) {
  return (
    <span className="rounded border border-border bg-surface px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em] text-text-muted">
      {status}
    </span>
  );
}

function isSettledSuccessStatus(status: string) {
  const normalized = status.trim().toLowerCase();
  return normalized === 'completed' || normalized === 'complete';
}

function TraceWarnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;

  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {warnings.map((warning) => (
        <span
          key={warning}
          className="inline-flex items-center gap-1 rounded border border-warning/30 bg-warning/10 px-1.5 py-0.5 text-[10px] text-warning"
        >
          <AlertTriangle className="h-3 w-3" aria-hidden="true" />
          {warning}
        </span>
      ))}
    </div>
  );
}

function isInternalWritingStatus(status: string) {
  const normalized = status.trim().toLowerCase().replace(/\.+$/, '');
  return (
    normalized === 'writing answer' || normalized === 'finalizing response'
  );
}

function isSafeMarkdownHref(href?: string) {
  if (!href) return false;
  const trimmed = href.trim();
  if (trimmed.startsWith('//')) return false;
  if (trimmed.startsWith('/') || trimmed.startsWith('#')) return true;
  try {
    const parsed = new URL(trimmed);
    return ['http:', 'https:', 'mailto:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}

function ChatMessageComponent({ message, onAction }: ChatMessageProps) {
  const { resolvedTheme } = useTheme();
  const { t } = useTranslation();
  const { config } = useInstanceConfig();
  const [copiedMessage, setCopiedMessage] = useState(false);
  const isUser = message.role === 'user';
  const label = isUser ? config.userLabel : config.assistantName;
  const visibleTraceStatus =
    message.traceStatus && !isInternalWritingStatus(message.traceStatus)
      ? message.traceStatus
      : null;
  const resolvedTraceDeltas =
    message.traceDeltas ?? message.trace?.trace_deltas ?? [];

  if (
    !isUser &&
    !message.content.trim() &&
    !visibleTraceStatus &&
    !isTraceRenderable(
      message.trace,
      visibleTraceStatus,
      message.activitySteps,
      resolvedTraceDeltas
    ) &&
    !(message.activitySteps && message.activitySteps.length > 0) &&
    resolvedTraceDeltas.length === 0
  ) {
    return null;
  }

  const handleCopyMessage = async () => {
    const copiedToClipboard = await copyTextToClipboard(message.content);
    if (!copiedToClipboard) return;
    setCopiedMessage(true);
    setTimeout(() => setCopiedMessage(false), 2000);
  };

  const bubbleStyles = {
    soft: {
      user: 'rounded-2xl rounded-tr-md',
      assistant: 'rounded-2xl rounded-tl-md',
    },
    round: {
      user: 'rounded-3xl',
      assistant: 'rounded-3xl',
    },
    square: {
      user: 'rounded-lg',
      assistant: 'rounded-lg',
    },
    pill: {
      user: 'rounded-3xl',
      assistant: 'rounded-3xl',
    },
  } as const;

  const bubbleRadius =
    bubbleStyles[config.chatBubbleStyle] || bubbleStyles.soft;
  const bubbleShadow = config.chatBubbleShadow ? 'shadow-sm' : '';
  const userBubbleClass = `group/message relative inline-block max-w-[min(88vw,42rem)] sm:max-w-[min(85%,42rem)] bg-accent text-accent-text px-4 py-2.5 pr-11 ${bubbleRadius.user} ${bubbleShadow}`;
  const assistantBubbleClass =
    'group/message relative w-full max-w-[48rem] px-1 py-1 pr-11';
  const copyButtonClass = isUser
    ? 'absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full text-accent-text/75 opacity-0 transition hover:bg-white/15 hover:text-accent-text hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 group-hover/message:opacity-80'
    : 'absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full text-text-muted opacity-0 transition hover:bg-surface-overlay hover:text-text hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 group-hover/message:opacity-80';
  const copyIcon = copiedMessage ? (
    <Check className="h-3.5 w-3.5" aria-hidden="true" />
  ) : (
    <Copy className="h-3.5 w-3.5" aria-hidden="true" />
  );
  const copyAction = (
    <button
      type="button"
      onClick={handleCopyMessage}
      className={copyButtonClass}
      aria-label={
        copiedMessage ? t('chat.messages.copied') : t('chat.messages.copy')
      }
      title={
        copiedMessage ? t('chat.messages.copied') : t('chat.messages.copy')
      }
    >
      {copyIcon}
    </button>
  );
  const messageActions =
    message.actions && message.actions.length > 0 ? (
      <div
        role="toolbar"
        aria-label={t('chat.messageActions')}
        className={`mt-1.5 flex items-center gap-1 ${isUser ? 'justify-end' : 'justify-start'}`}
      >
        {message.actions.map((action) => (
          <button
            key={action.id}
            type="button"
            onClick={() => {
              if (!action.disabled) onAction?.(action.id, message);
            }}
            disabled={action.disabled}
            aria-label={action.label}
            title={action.disabledReason ?? action.label}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-overlay hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-transparent disabled:hover:text-text-muted"
          >
            <MessageActionIcon actionId={action.id} />
          </button>
        ))}
      </div>
    ) : null;

  return (
    <div className="animate-fade-in-up mb-4 last:mb-0">
      <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
        {/* Avatar */}
        {isUser ? (
          <UserIcon iconName={config.userIcon} />
        ) : (
          <AssistantIcon iconName={config.assistantIcon} />
        )}

        {/* Content */}
        <div
          className={`flex-1 min-w-0 ${isUser ? 'flex flex-col items-end' : 'flex flex-col items-start'}`}
        >
          {label?.trim() && isUser && (
            <div className="text-xs text-text-muted mb-1">{label}</div>
          )}
          {isUser ? (
            <>
              <div className={userBubbleClass}>
                {copyAction}
                <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed">
                  {message.content}
                </p>
              </div>
              {messageActions}
            </>
          ) : (
            <>
              <div className={assistantBubbleClass}>
                {copyAction}
                <div className="text-text break-words [&_*]:text-inherit [&_a]:text-accent [&_code]:text-text">
                  <ConversationTracePanel
                    trace={message.trace}
                    activitySteps={message.activitySteps}
                    traceDeltas={resolvedTraceDeltas}
                    liveStatus={visibleTraceStatus}
                    isStreaming={Boolean(message.traceStatus)}
                  />
                  {message.content.trim() && (
                    <div
                      className={
                        message.trace ||
                        visibleTraceStatus ||
                        (message.activitySteps &&
                          message.activitySteps.length > 0) ||
                        resolvedTraceDeltas.length > 0
                          ? 'mt-3'
                          : ''
                      }
                    >
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({ node, className, children, ...props }) {
                            const match = /language-([\w+-]+)/.exec(
                              className || ''
                            );
                            const isInline = !match && !className;

                            if (isInline) {
                              return (
                                <code
                                  className="bg-surface-overlay px-1.5 py-0.5 rounded text-[0.875em] font-mono text-text"
                                  {...props}
                                >
                                  {children}
                                </code>
                              );
                            }

                            return (
                              <CodeBlock
                                language={match ? match[1] : null}
                                resolvedTheme={resolvedTheme}
                              >
                                {String(children).replace(/\n$/, '')}
                              </CodeBlock>
                            );
                          },
                          p({ children }) {
                            return (
                              <p className="mb-3 last:mb-0 text-[15px] leading-relaxed">
                                {children}
                              </p>
                            );
                          },
                          a({ href, children }) {
                            if (!isSafeMarkdownHref(href)) {
                              return <span>{children}</span>;
                            }
                            return (
                              <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-accent hover:text-accent-hover underline underline-offset-2 decoration-accent/30 hover:decoration-accent transition-colors"
                              >
                                {children}
                              </a>
                            );
                          },
                          ul({ children }) {
                            return (
                              <ul className="mb-3 last:mb-0 list-disc space-y-1.5 pl-5 text-[15px]">
                                {children}
                              </ul>
                            );
                          },
                          ol({ children }) {
                            return (
                              <ol className="mb-3 last:mb-0 list-decimal space-y-1.5 pl-5 text-[15px]">
                                {children}
                              </ol>
                            );
                          },
                          li({ children }) {
                            return (
                              <li className="pl-1 leading-relaxed marker:text-accent">
                                {children}
                              </li>
                            );
                          },
                          blockquote({ children }) {
                            return (
                              <blockquote className="my-4 border-l-4 border-border pl-4 text-text-secondary text-[15px] leading-relaxed [&>p]:mb-0">
                                {children}
                              </blockquote>
                            );
                          },
                          em({ children }) {
                            return (
                              <em className="italic text-inherit">
                                {children}
                              </em>
                            );
                          },
                          h1({ children }) {
                            return (
                              <h1 className="text-xl font-semibold mb-3 mt-4 first:mt-0 text-text tracking-tight">
                                {children}
                              </h1>
                            );
                          },
                          h2({ children }) {
                            return (
                              <h2 className="text-lg font-semibold mb-2 mt-4 first:mt-0 text-text tracking-tight">
                                {children}
                              </h2>
                            );
                          },
                          h3({ children }) {
                            return (
                              <h3 className="text-base font-semibold mb-2 mt-3 first:mt-0 text-text tracking-tight">
                                {children}
                              </h3>
                            );
                          },
                          hr() {
                            return <hr className="my-4 border-border" />;
                          },
                          strong({ children }) {
                            return (
                              <strong className="font-semibold text-text">
                                {children}
                              </strong>
                            );
                          },
                          table({ children }) {
                            return (
                              <div className="my-4 overflow-x-auto rounded-xl border border-border shadow-sm">
                                <table className="min-w-full text-sm divide-y divide-border">
                                  {children}
                                </table>
                              </div>
                            );
                          },
                          thead({ children }) {
                            return (
                              <thead className="bg-surface-raised">
                                {children}
                              </thead>
                            );
                          },
                          tbody({ children }) {
                            return (
                              <tbody className="divide-y divide-border bg-surface">
                                {children}
                              </tbody>
                            );
                          },
                          tr({ children }) {
                            return (
                              <tr className="hover:bg-surface-overlay transition-colors duration-150 even:bg-surface-raised/50">
                                {children}
                              </tr>
                            );
                          },
                          th({ children }) {
                            return (
                              <th className="px-4 py-3 text-left text-xs font-semibold text-text uppercase tracking-wider">
                                {children}
                              </th>
                            );
                          },
                          td({ children }) {
                            return (
                              <td className="px-4 py-3 text-text-secondary">
                                {children}
                              </td>
                            );
                          },
                        }}
                      >
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
              {messageActions}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// Memoized so a streaming turn only re-renders the active message, not the whole
// list. patchAssistantMessage keeps non-streaming messages by reference, so their
// markdown + syntax highlighting is not recomputed on every token.
export const ChatMessage = memo(ChatMessageComponent);

function MessageActionIcon({
  actionId,
}: {
  actionId: ConversationMessageActionId;
}) {
  if (actionId === 'stop') {
    return <Square className="h-3.5 w-3.5" aria-hidden="true" />;
  }
  if (actionId === 'regenerate') {
    return <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />;
  }
  return <Pencil className="h-3.5 w-3.5" aria-hidden="true" />;
}
