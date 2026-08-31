import { type ReactElement, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Bot,
  CheckCircle2,
  Database,
  KeyRound,
  LifeBuoy,
  Mail,
  MessageCircle,
  Paintbrush,
  Search,
  Server,
  Settings2,
  ShieldCheck,
  Upload,
  UserCheck,
  Users,
  Wand2,
} from 'lucide-react';
import { PageShell } from '../components/ui';
import { cx } from '../components/ui/utils';

interface SummaryCard {
  title: string;
  body: string;
  to: string;
  icon: ReactElement;
}

interface GuideCard {
  eyebrow: string;
  title: string;
  body: string;
  details: string[];
  to?: string;
  linkLabel?: string;
  icon: ReactElement;
}

const interactiveCardClassName = cx(
  'focus-ring group flex h-full flex-col rounded-2xl bg-surface-raised p-5 shadow-sm ring-1 ring-border/70',
  'transition-[transform,box-shadow,background-color] duration-200 ease-out',
  'hover:-translate-y-0.5 hover:bg-surface-overlay hover:shadow-md active:scale-[0.96]'
);

const summaryCardClassName = cx(
  'focus-ring group flex min-h-32 flex-col justify-between rounded-2xl bg-surface p-4 text-left shadow-sm ring-1 ring-border/70',
  'transition-[transform,box-shadow,background-color] duration-200 ease-out',
  'hover:-translate-y-0.5 hover:bg-surface-overlay hover:shadow-md active:scale-[0.96]'
);

const infoCardClassName =
  'rounded-2xl bg-surface-raised p-5 shadow-sm ring-1 ring-border/70';

const quickSteps = [0, 1, 2, 3, 4] as const;
const safetyBasics = [0, 1, 2, 3, 4] as const;

export function AdminGuides() {
  const { t } = useTranslation();
  const adminsCanLabel = t('adminGuides.card.adminsCan', 'Admins can');

  const summaryCards: SummaryCard[] = [
    {
      to: '/admin/instance',
      title: t('adminGuides.summary.brand.title', 'Brand the instance'),
      body: t(
        'adminGuides.summary.brand.body',
        'Name, logo, theme, assistant identity, and public email display.'
      ),
      icon: <Paintbrush className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/users',
      title: t('adminGuides.summary.people.title', 'Control people'),
      body: t(
        'adminGuides.summary.people.body',
        'User types, onboarding questions, approvals, migration, and access.'
      ),
      icon: <Users className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/ai',
      title: t('adminGuides.summary.agent.title', 'Shape Sage'),
      body: t(
        'adminGuides.summary.agent.body',
        'Prompt rules, response settings, document access, and tool defaults.'
      ),
      icon: <Bot className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/deployment',
      title: t('adminGuides.summary.launch.title', 'Launch safely'),
      body: t(
        'adminGuides.summary.launch.body',
        'Email, domains, CORS, HTTPS, model routing, health, and runtime env.'
      ),
      icon: <Server className="h-5 w-5" aria-hidden="true" />,
    },
  ];

  const configureCards: GuideCard[] = [
    {
      to: '/admin/instance',
      eyebrow: t('adminGuides.configure.identity.eyebrow', 'Brand'),
      title: t('adminGuides.configure.identity.title', 'Identity and look'),
      body: t(
        'adminGuides.configure.identity.body',
        'Make the instance feel like your organization.'
      ),
      details: [
        t(
          'adminGuides.configure.identity.detail1',
          'Name, tagline, assistant name, and user label.'
        ),
        t(
          'adminGuides.configure.identity.detail2',
          'Logo, favicon, icon, accent color, theme, typography, and chat style.'
        ),
        t(
          'adminGuides.configure.identity.detail3',
          'Default language and public email display name.'
        ),
      ],
      linkLabel: t(
        'adminGuides.configure.identity.link',
        'Open Instance Settings'
      ),
      icon: <Paintbrush className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/users',
      eyebrow: t('adminGuides.configure.people.eyebrow', 'Access'),
      title: t('adminGuides.configure.people.title', 'People and access'),
      body: t(
        'adminGuides.configure.people.body',
        'Decide who uses the instance and what you ask them.'
      ),
      details: [
        t(
          'adminGuides.configure.people.detail1',
          'User types for groups like staff, members, or clients.'
        ),
        t(
          'adminGuides.configure.people.detail2',
          'Onboarding fields, required questions, options, placeholders, and per-type fields.'
        ),
        t(
          'adminGuides.configure.people.detail3',
          'Manual approval, user migration, revoking access, and deletion.'
        ),
      ],
      linkLabel: t('adminGuides.configure.people.link', 'Open User Settings'),
      icon: <Users className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/ai',
      eyebrow: t('adminGuides.configure.agent.eyebrow', 'Behavior'),
      title: t('adminGuides.configure.agent.title', 'Agent behavior'),
      body: t(
        'adminGuides.configure.agent.body',
        'Shape how Sage answers and which tools are on by default.'
      ),
      details: [
        t(
          'adminGuides.configure.agent.detail1',
          'Prompt template, behavior rules, forbidden topics, and response settings.'
        ),
        t(
          'adminGuides.configure.agent.detail2',
          'Feature defaults for Knowledge, Resources, Web, Config, and Database tools.'
        ),
        t(
          'adminGuides.configure.agent.detail3',
          'Global settings plus user-type overrides.'
        ),
      ],
      linkLabel: t('adminGuides.configure.agent.link', 'Open Agent Settings'),
      icon: <Bot className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/upload',
      eyebrow: t('adminGuides.configure.docs.eyebrow', 'Knowledge'),
      title: t('adminGuides.configure.docs.title', 'Document knowledge'),
      body: t(
        'adminGuides.configure.docs.body',
        'Give the agent source material it can search.'
      ),
      details: [
        t(
          'adminGuides.configure.docs.detail1',
          'Upload PDFs, policies, FAQs, handbooks, and guides.'
        ),
        t(
          'adminGuides.configure.docs.detail2',
          'Documents are chunked, embedded, and made searchable.'
        ),
        t(
          'adminGuides.configure.docs.detail3',
          'Document Access controls what can be selected or active by default.'
        ),
      ],
      linkLabel: t('adminGuides.configure.docs.link', 'Open Document Upload'),
      icon: <Upload className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/resources',
      eyebrow: t('adminGuides.configure.resources.eyebrow', 'Referrals'),
      title: t('adminGuides.configure.resources.title', 'Vetted resources'),
      body: t(
        'adminGuides.configure.resources.body',
        'Add trusted referrals the agent can recommend.'
      ),
      details: [
        t(
          'adminGuides.configure.resources.detail1',
          'Names, descriptions, resource type, languages, coverage, and help types.'
        ),
        t(
          'adminGuides.configure.resources.detail2',
          'Phone, email, URL, secure channel, address, and notes.'
        ),
        t(
          'adminGuides.configure.resources.detail3',
          'Verified resources rank first. Archived resources stay hidden from users.'
        ),
      ],
      linkLabel: t(
        'adminGuides.configure.resources.link',
        'Open Resource Directory'
      ),
      icon: <LifeBuoy className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/deployment',
      eyebrow: t('adminGuides.configure.ops.eyebrow', 'Operations'),
      title: t('adminGuides.configure.ops.title', 'Operations and runtime'),
      body: t(
        'adminGuides.configure.ops.body',
        'Keep the instance connected, reachable, and healthy.'
      ),
      details: [
        t(
          'adminGuides.configure.ops.detail1',
          'SMTP for email magic links, domains, CORS, HTTPS, and public URLs.'
        ),
        t(
          'adminGuides.configure.ops.detail2',
          'Model provider, embedding model, search, storage, and service health.'
        ),
        t(
          'adminGuides.configure.ops.detail3',
          'Runtime env export, readiness, stale settings, and admin key migration.'
        ),
      ],
      linkLabel: t(
        'adminGuides.configure.ops.link',
        'Open Deployment Settings'
      ),
      icon: <Server className="h-5 w-5" aria-hidden="true" />,
    },
  ];

  const workflowCards: GuideCard[] = [
    {
      to: '/chat',
      eyebrow: t('adminGuides.workflows.assistant.eyebrow', 'Ask'),
      title: t('adminGuides.workflows.assistant.title', 'Admin Assistant'),
      body: t(
        'adminGuides.workflows.assistant.body',
        'Ask questions about current setup and request config changes.'
      ),
      details: [
        t(
          'adminGuides.workflows.assistant.detail1',
          'Config reads inspect real instance state instead of guessing.'
        ),
        t(
          'adminGuides.workflows.assistant.directWriteDetail2',
          'Sage asks for conversational confirmation before a supported write.'
        ),
        t(
          'adminGuides.workflows.assistant.directWriteDetail3',
          'After you confirm, Sage calls its direct configuration Tools and reports the real result.'
        ),
      ],
      linkLabel: t(
        'adminGuides.workflows.assistant.link',
        'Open Admin Assistant'
      ),
      icon: <MessageCircle className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/onboarding',
      eyebrow: t('adminGuides.workflows.guided.eyebrow', 'Start'),
      title: t('adminGuides.workflows.guided.title', 'Guided Setup'),
      body: t(
        'adminGuides.workflows.guided.body',
        'Use one guided chat to create a useful first configuration.'
      ),
      details: [
        t(
          'adminGuides.workflows.guided.detail1',
          'Identity, assistant, language, access policy, user types, questions, and behavior rules.'
        ),
        t(
          'adminGuides.workflows.guided.detail2',
          'Then upload docs, add resources, and test.'
        ),
      ],
      linkLabel: t('adminGuides.workflows.guided.link', 'Open Guided Setup'),
      icon: <Wand2 className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/test-and-feedback',
      eyebrow: t('adminGuides.workflows.test.eyebrow', 'Validate'),
      title: t('adminGuides.workflows.test.title', 'Test and feedback'),
      body: t(
        'adminGuides.workflows.test.body',
        'Try the agent from a user point of view before launch.'
      ),
      details: [
        t(
          'adminGuides.workflows.test.detail1',
          'Pick a user type, start a test session, and save the trial.'
        ),
        t(
          'adminGuides.workflows.test.detail2',
          'Review encrypted beta logs and rate answers.'
        ),
      ],
      linkLabel: t('adminGuides.workflows.test.link', 'Open Test User Session'),
      icon: <UserCheck className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/admin/database',
      eyebrow: t('adminGuides.workflows.database.eyebrow', 'Inspect'),
      title: t('adminGuides.workflows.database.title', 'Database Explorer'),
      body: t(
        'adminGuides.workflows.database.body',
        'Inspect stored SQLite data when debugging.'
      ),
      details: [
        t(
          'adminGuides.workflows.database.detail1',
          'Use read-only SELECT queries for inspection.'
        ),
        t(
          'adminGuides.workflows.database.detail2',
          'Do not use it as a product mutation path.'
        ),
      ],
      linkLabel: t(
        'adminGuides.workflows.database.link',
        'Open Database Explorer'
      ),
      icon: <Database className="h-5 w-5" aria-hidden="true" />,
    },
  ];

  const truthCards: GuideCard[] = [
    {
      eyebrow: t('adminGuides.truths.conversation.eyebrow', 'Runtime'),
      title: t(
        'adminGuides.truths.conversation.title',
        'One conversation runtime'
      ),
      body: t(
        'adminGuides.truths.conversation.body',
        'Knowledge, Resources, Web, Config, and Database are visible tool sets, not separate chat systems.'
      ),
      details: [
        t(
          'adminGuides.truths.conversation.detail1',
          'The model can call enabled tools when they help.'
        ),
        t(
          'adminGuides.truths.conversation.detail2',
          'Config and Database only appear for server-validated admins.'
        ),
      ],
      icon: <Settings2 className="h-5 w-5" aria-hidden="true" />,
    },
    {
      eyebrow: t('adminGuides.truths.auth.eyebrow', 'Sign-in'),
      title: t('adminGuides.truths.auth.title', 'Different sign-in paths'),
      body: t(
        'adminGuides.truths.auth.body',
        'Admins use NIP-07. Users use email magic links.'
      ),
      details: [
        t(
          'adminGuides.truths.auth.detail1',
          'Admin private keys stay in the browser signer.'
        ),
        t(
          'adminGuides.truths.auth.detail2',
          'SMTP must work before user magic links work in production.'
        ),
      ],
      icon: <KeyRound className="h-5 w-5" aria-hidden="true" />,
    },
    {
      eyebrow: t('adminGuides.truths.data.eyebrow', 'Privacy'),
      title: t('adminGuides.truths.data.title', 'Data boundaries matter'),
      body: t(
        'adminGuides.truths.data.body',
        'Encrypted profile fields stay out of chat context.'
      ),
      details: [
        t(
          'adminGuides.truths.data.detail1',
          'Only unencrypted fields can be marked for AI chat context.'
        ),
        t(
          'adminGuides.truths.data.detail2',
          'Deployment secrets are stored encrypted and shown masked by default.'
        ),
      ],
      icon: <ShieldCheck className="h-5 w-5" aria-hidden="true" />,
    },
    {
      eyebrow: t('adminGuides.truths.ops.eyebrow', 'Ops'),
      title: t('adminGuides.truths.ops.title', 'Some changes need operators'),
      body: t(
        'adminGuides.truths.ops.body',
        'The app can save desired runtime settings; it does not silently restart services.'
      ),
      details: [
        t(
          'adminGuides.truths.ops.detail1',
          'Export runtime env after provider, origin, CORS, or search changes.'
        ),
        t(
          'adminGuides.truths.ops.detail2',
          'Use readiness and service health to confirm what is actually running.'
        ),
      ],
      icon: <Mail className="h-5 w-5" aria-hidden="true" />,
    },
  ];

  const askPrompts = [
    t(
      'adminGuides.ask.prompt1',
      'What is still missing before this instance is ready for users?'
    ),
    t(
      'adminGuides.ask.prompt2',
      'Review the current user types, onboarding questions, docs, and resources.'
    ),
    t(
      'adminGuides.ask.directWritePrompt3',
      'Set the assistant tone and default language, and confirm the intended change with me first.'
    ),
  ];

  return (
    <PageShell
      width="xl"
      className="bg-surface"
      header={
        <div className="flex flex-col gap-5">
          <Link
            to="/admin/setup"
            className="focus-ring inline-flex min-h-10 w-fit items-center gap-2 rounded-xl px-2.5 text-sm font-medium text-text-secondary transition-[background-color,color,transform] duration-150 ease-out hover:bg-surface-overlay hover:text-text active:scale-[0.96]"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            {t('common.backToAdminDashboard', 'Back to Admin Dashboard')}
          </Link>

          <section className="rounded-3xl bg-surface-raised p-6 shadow-md ring-1 ring-border/70 sm:p-8">
            <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
              <div className="max-w-3xl">
                <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 text-accent ring-1 ring-accent/20">
                  <BookOpen className="h-7 w-7" aria-hidden="true" />
                </div>
                <p className="mb-3 text-xs font-semibold uppercase tracking-normal text-accent">
                  {t('adminGuides.hero.eyebrow', 'Admin control map')}
                </p>
                <h1 className="text-balance text-2xl font-semibold tracking-normal text-text">
                  {t('adminGuides.title', 'Admin Guides')}
                </h1>
                <p className="mt-3 max-w-2xl text-pretty text-base leading-7 text-text-secondary">
                  {t(
                    'adminGuides.subtitle',
                    'A simple map of what admins configure, what the product can do, and what needs care before launch.'
                  )}
                </p>
              </div>

              <div className="rounded-2xl bg-surface p-4 [box-shadow:var(--shadow-inner-sm)] ring-1 ring-border/60">
                <p className="text-sm font-semibold text-text">
                  {t('adminGuides.hero.shortVersion.title', 'Short version')}
                </p>
                <p className="mt-2 text-pretty text-sm leading-6 text-text-secondary">
                  {t(
                    'adminGuides.hero.shortVersion.body',
                    'Admins set the identity, users, knowledge, tools, and launch settings. Some runtime changes still need an operator restart.'
                  )}
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {summaryCards.map((card) => (
                <SummaryLink key={card.title} card={card} />
              ))}
            </div>
          </section>
        </div>
      }
    >
      <GuideSection
        id="quick-start"
        icon={<CheckCircle2 className="h-5 w-5" aria-hidden="true" />}
        title={t('adminGuides.quickStart.title', 'Start here')}
        description={t(
          'adminGuides.quickStart.body',
          'Do the small useful setup first. Polish it after testing with real questions.'
        )}
      >
        <ol className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {quickSteps.map((stepIndex) => (
            <li
              key={`adminGuides.quickSteps.${stepIndex}`}
              className="rounded-2xl bg-surface-raised p-5 shadow-sm ring-1 ring-border/70"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-sm font-semibold tabular-nums text-accent ring-1 ring-accent/15">
                  {stepIndex + 1}
                </span>
                <h3 className="text-balance text-base font-semibold text-text">
                  {t(`adminGuides.quickSteps.${stepIndex}.title`)}
                </h3>
              </div>
              <p className="mt-3 text-pretty text-sm leading-6 text-text-secondary">
                {t(`adminGuides.quickSteps.${stepIndex}.body`)}
              </p>
            </li>
          ))}
        </ol>
      </GuideSection>

      <GuideSection
        id="configure"
        icon={<Paintbrush className="h-5 w-5" aria-hidden="true" />}
        title={t('adminGuides.configure.title', 'What admins configure')}
        description={t(
          'adminGuides.configure.body',
          'These are the main control surfaces. You can use the pages directly or ask the Admin Assistant to prepare changes.'
        )}
      >
        <div className="grid gap-4 lg:grid-cols-2">
          {configureCards.map((card) => (
            <GuideLinkCard
              key={card.title}
              card={card}
              adminsCanLabel={adminsCanLabel}
            />
          ))}
        </div>
      </GuideSection>

      <GuideSection
        id="workflows"
        icon={<Search className="h-5 w-5" aria-hidden="true" />}
        title={t('adminGuides.workflows.title', 'Common admin workflows')}
        description={t(
          'adminGuides.workflows.body',
          'Use these when you are setting up, checking quality, or investigating data.'
        )}
      >
        <div className="grid gap-4 lg:grid-cols-4">
          {workflowCards.map((card) => (
            <GuideLinkCard
              key={card.title}
              card={card}
              compact
              adminsCanLabel={adminsCanLabel}
            />
          ))}
        </div>
      </GuideSection>

      <GuideSection
        id="truths"
        icon={<ShieldCheck className="h-5 w-5" aria-hidden="true" />}
        title={t('adminGuides.truths.title', 'Product truths to remember')}
        description={t(
          'adminGuides.truths.body',
          'These rules keep setup honest and prevent accidental overreach.'
        )}
      >
        <div className="grid gap-4 lg:grid-cols-2">
          {truthCards.map((card) => (
            <GuideInfoCard
              key={card.title}
              card={card}
              adminsCanLabel={adminsCanLabel}
            />
          ))}
        </div>
      </GuideSection>

      <section
        className="rounded-3xl bg-surface-raised p-6 shadow-md ring-1 ring-border/70 sm:p-7"
        aria-labelledby="safety-basics"
      >
        <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr] lg:items-start">
          <div>
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent ring-1 ring-accent/15">
              <ShieldCheck className="h-6 w-6" aria-hidden="true" />
            </div>
            <h2
              id="safety-basics"
              className="text-balance text-xl font-semibold tracking-normal text-text"
            >
              {t('adminGuides.safety.title', 'Safety basics')}
            </h2>
            <p className="mt-2 text-pretty text-sm leading-6 text-text-secondary">
              {t(
                'adminGuides.safety.body',
                'Admins control access, data, behavior, and runtime settings. Go slow with risky changes.'
              )}
            </p>
          </div>
          <ul className="grid gap-3">
            {safetyBasics.map((itemIndex) => (
              <li
                key={`adminGuides.safety.directItems.${itemIndex}`}
                className="flex items-start gap-3 rounded-2xl bg-surface p-4 text-sm leading-6 text-text-secondary ring-1 ring-border/60"
              >
                <CheckCircle2
                  className="mt-0.5 h-5 w-5 shrink-0 text-success"
                  aria-hidden="true"
                />
                <span className="text-pretty">
                  {t(`adminGuides.safety.directItems.${itemIndex}`)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <GuideSection
        id="ask"
        icon={<MessageCircle className="h-5 w-5" aria-hidden="true" />}
        title={t(
          'adminGuides.ask.title',
          'Good things to ask the Admin Assistant'
        )}
        description={t(
          'adminGuides.ask.directWriteBody',
          'Ask Sage to inspect or change supported configuration. It will confirm the intended change with you before writing.'
        )}
      >
        <div className="grid gap-4 md:grid-cols-3">
          {askPrompts.map((prompt) => (
            <div
              key={prompt}
              className="rounded-2xl bg-surface-raised p-5 shadow-sm ring-1 ring-border/70"
            >
              <MessageCircle
                className="mb-4 h-5 w-5 text-accent"
                aria-hidden="true"
              />
              <p className="text-pretty text-sm leading-6 text-text-secondary">
                {prompt}
              </p>
            </div>
          ))}
        </div>
      </GuideSection>
    </PageShell>
  );
}

function SummaryLink({ card }: { card: SummaryCard }) {
  return (
    <Link to={card.to} className={summaryCardClassName}>
      <div>
        <IconFrame size="sm" className="mb-3">
          {card.icon}
        </IconFrame>
        <h2 className="text-balance text-sm font-semibold text-text">
          {card.title}
        </h2>
        <p className="mt-1 text-pretty text-xs leading-5 text-text-secondary">
          {card.body}
        </p>
      </div>
      <ArrowRight
        className="mt-4 h-4 w-4 text-text-muted transition-transform duration-150 ease-out group-hover:translate-x-0.5 group-hover:text-accent"
        aria-hidden="true"
      />
    </Link>
  );
}

function GuideSection({
  id,
  icon,
  title,
  description,
  children,
}: {
  id: string;
  icon: ReactNode;
  title: ReactNode;
  description: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-5" aria-labelledby={id}>
      <div className="flex max-w-3xl items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent ring-1 ring-accent/15">
          {icon}
        </div>
        <div className="min-w-0">
          <h2
            id={id}
            className="text-balance text-xl font-semibold tracking-normal text-text"
          >
            {title}
          </h2>
          <p className="mt-2 text-pretty text-sm leading-6 text-text-secondary">
            {description}
          </p>
        </div>
      </div>
      {children}
    </section>
  );
}

function GuideLinkCard({
  card,
  compact = false,
  adminsCanLabel,
}: {
  card: GuideCard;
  compact?: boolean;
  adminsCanLabel: string;
}) {
  return (
    <Link to={card.to ?? '/admin/setup'} className={interactiveCardClassName}>
      <GuideCardContent
        card={card}
        compact={compact}
        adminsCanLabel={adminsCanLabel}
      />
      <div className="mt-auto flex min-h-10 items-center gap-2 pt-4 text-sm font-medium text-accent">
        <span>{card.linkLabel}</span>
        <ArrowRight
          className="h-4 w-4 transition-transform duration-150 ease-out group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </Link>
  );
}

function GuideInfoCard({
  card,
  adminsCanLabel,
}: {
  card: GuideCard;
  adminsCanLabel: string;
}) {
  return (
    <article className={infoCardClassName}>
      <GuideCardContent card={card} adminsCanLabel={adminsCanLabel} />
    </article>
  );
}

function GuideCardContent({
  card,
  compact = false,
  adminsCanLabel,
}: {
  card: GuideCard;
  compact?: boolean;
  adminsCanLabel: string;
}) {
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="flex items-start gap-4">
        <IconFrame>{card.icon}</IconFrame>
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold uppercase tracking-normal text-accent">
            {card.eyebrow}
          </p>
          <h3 className="text-balance text-base font-semibold text-text">
            {card.title}
          </h3>
          <p className="mt-2 text-pretty text-sm leading-6 text-text-secondary">
            {card.body}
          </p>
        </div>
      </div>

      <div className="rounded-2xl bg-surface p-4 ring-1 ring-border/60">
        <p className="mb-3 text-xs font-semibold uppercase tracking-normal text-text-muted">
          {adminsCanLabel}
        </p>
        <ul className={compact ? 'space-y-2' : 'grid gap-2'}>
          {card.details.map((detail) => (
            <li
              key={detail}
              className="flex items-start gap-2 text-sm leading-6 text-text-secondary"
            >
              <CheckCircle2
                className="mt-1 h-4 w-4 shrink-0 text-success"
                aria-hidden="true"
              />
              <span className="text-pretty">{detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function IconFrame({
  children,
  className,
  size = 'md',
}: {
  children: ReactNode;
  className?: string;
  size?: 'sm' | 'md';
}) {
  return (
    <div
      className={cx(
        'flex shrink-0 items-center justify-center bg-accent/10 text-accent ring-1 ring-accent/15',
        size === 'sm' ? 'h-10 w-10 rounded-xl' : 'h-12 w-12 rounded-2xl',
        className
      )}
    >
      {children}
    </div>
  );
}
