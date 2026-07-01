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
import { PageShell, SectionHeader } from '../components/ui';

interface Step {
  title: string;
  body: string;
}

interface GuideCard {
  title: string;
  body: string;
  details: string[];
  to?: string;
  linkLabel?: string;
  icon: JSX.Element;
}

const quickSteps: Step[] = [
  {
    title: 'Sign in as admin',
    body: 'Use the admin NIP-07 key. Keep it private.',
  },
  {
    title: 'Set the basics',
    body: 'Name the instance, choose the look, and set the assistant identity.',
  },
  {
    title: 'Define your users',
    body: 'Create user types, onboarding questions, and approval rules.',
  },
  {
    title: 'Add trusted knowledge',
    body: 'Upload documents and add vetted resources.',
  },
  {
    title: 'Test before launch',
    body: 'Chat as a user, review feedback, then invite real people.',
  },
];

const safetyBasics = [
  'Admins sign in with NIP-07. Users sign in with email magic links.',
  'User fields are encrypted by default. Only plaintext fields can be shared with chat.',
  'Secrets stay masked unless you share them for the current admin session.',
  'Assistant changes are proposals. You still review and click Apply.',
  'Deployment Settings store desired runtime values. Operators still export env and restart services when needed.',
];

export function AdminGuides() {
  const { t } = useTranslation();

  const configureCards: GuideCard[] = [
    {
      to: '/admin/instance',
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
      icon: <Paintbrush className="h-5 w-5" />,
    },
    {
      to: '/admin/users',
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
      icon: <Users className="h-5 w-5" />,
    },
    {
      to: '/admin/ai',
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
      icon: <Bot className="h-5 w-5" />,
    },
    {
      to: '/admin/upload',
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
      icon: <Upload className="h-5 w-5" />,
    },
    {
      to: '/admin/resources',
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
      icon: <LifeBuoy className="h-5 w-5" />,
    },
    {
      to: '/admin/deployment',
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
      icon: <Server className="h-5 w-5" />,
    },
  ];

  const workflowCards: GuideCard[] = [
    {
      to: '/chat',
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
          'adminGuides.workflows.assistant.detail2',
          'Proposed changes are staged for review.'
        ),
        t(
          'adminGuides.workflows.assistant.detail3',
          'Apply runs the approved admin endpoints without another model turn.'
        ),
      ],
      linkLabel: t(
        'adminGuides.workflows.assistant.link',
        'Open Admin Assistant'
      ),
      icon: <MessageCircle className="h-5 w-5" />,
    },
    {
      to: '/admin/onboarding',
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
      icon: <Wand2 className="h-5 w-5" />,
    },
    {
      to: '/admin/test-and-feedback',
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
      icon: <UserCheck className="h-5 w-5" />,
    },
    {
      to: '/admin/database',
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
      icon: <Database className="h-5 w-5" />,
    },
  ];

  const truthCards: GuideCard[] = [
    {
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
      icon: <Settings2 className="h-5 w-5" />,
    },
    {
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
      icon: <KeyRound className="h-5 w-5" />,
    },
    {
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
      icon: <ShieldCheck className="h-5 w-5" />,
    },
    {
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
      icon: <Mail className="h-5 w-5" />,
    },
  ];

  return (
    <PageShell
      width="xl"
      className="bg-surface"
      header={
        <div className="flex flex-col gap-4">
          <Link
            to="/admin/setup"
            className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text"
          >
            <ArrowLeft className="h-4 w-4" />
            {t('common.backToAdminDashboard', 'Back to Admin Dashboard')}
          </Link>
          <SectionHeader
            icon={<BookOpen className="h-5 w-5" />}
            title={t('adminGuides.title', 'Admin Guides')}
            description={t(
              'adminGuides.subtitle',
              'A simple map of what admins configure, what the product can do, and what needs care before launch.'
            )}
          />
        </div>
      }
    >
      <section className="flex flex-col gap-4" aria-labelledby="quick-start">
        <SectionHeader
          icon={<CheckCircle2 className="h-5 w-5" />}
          title={
            <span id="quick-start">
              {t('adminGuides.quickStart.title', 'Start here')}
            </span>
          }
          description={t(
            'adminGuides.quickStart.body',
            'Do the small useful setup first. Polish it after testing with real questions.'
          )}
        />

        <ol className="grid gap-3 md:grid-cols-5">
          {quickSteps.map((step, index) => (
            <li
              key={step.title}
              className="rounded-lg border border-border bg-surface-raised p-4"
            >
              <div className="text-xs font-semibold uppercase tracking-normal text-accent">
                {t('adminGuides.stepLabel', 'Step')} {index + 1}
              </div>
              <h3 className="mt-2 text-sm font-semibold text-text">
                {t(`adminGuides.quickSteps.${index}.title`, step.title)}
              </h3>
              <p className="mt-1 text-xs leading-5 text-text-secondary">
                {t(`adminGuides.quickSteps.${index}.body`, step.body)}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="configure">
        <SectionHeader
          icon={<Paintbrush className="h-5 w-5" />}
          title={
            <span id="configure">
              {t('adminGuides.configure.title', 'What admins configure')}
            </span>
          }
          description={t(
            'adminGuides.configure.body',
            'These are the main control surfaces. You can use the pages directly or ask the Admin Assistant to prepare changes.'
          )}
        />

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {configureCards.map((card) => (
            <GuideLinkCard key={card.title} card={card} />
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="workflows">
        <SectionHeader
          icon={<Search className="h-5 w-5" />}
          title={
            <span id="workflows">
              {t('adminGuides.workflows.title', 'Common admin workflows')}
            </span>
          }
          description={t(
            'adminGuides.workflows.body',
            'Use these when you are setting up, checking quality, or investigating data.'
          )}
        />

        <div className="grid gap-3 md:grid-cols-2">
          {workflowCards.map((card) => (
            <GuideLinkCard key={card.title} card={card} />
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="truths">
        <SectionHeader
          icon={<ShieldCheck className="h-5 w-5" />}
          title={
            <span id="truths">
              {t('adminGuides.truths.title', 'Product truths to remember')}
            </span>
          }
          description={t(
            'adminGuides.truths.body',
            'These rules keep setup honest and prevent accidental overreach.'
          )}
        />

        <div className="grid gap-3 md:grid-cols-2">
          {truthCards.map((card) => (
            <GuideInfoCard key={card.title} card={card} />
          ))}
        </div>
      </section>

      <section
        className="rounded-lg border border-border bg-surface-raised p-5"
        aria-labelledby="safety-basics"
      >
        <div className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
          <div>
            <h2
              id="safety-basics"
              className="text-base font-semibold text-text"
            >
              {t('adminGuides.safety.title', 'Safety basics')}
            </h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              {t(
                'adminGuides.safety.body',
                'Admins control access, data, behavior, and runtime settings. Go slow with risky changes.'
              )}
            </p>
          </div>
        </div>
        <ul className="mt-4 grid gap-2 md:grid-cols-2">
          {safetyBasics.map((item, index) => (
            <li
              key={item}
              className="flex items-start gap-2 text-sm leading-6 text-text-secondary"
            >
              <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-success" />
              <span>{t(`adminGuides.safety.items.${index}`, item)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="ask">
        <SectionHeader
          icon={<MessageCircle className="h-5 w-5" />}
          title={
            <span id="ask">
              {t(
                'adminGuides.ask.title',
                'Good things to ask the Admin Assistant'
              )}
            </span>
          }
          description={t(
            'adminGuides.ask.body',
            'Ask for a review before asking for changes. It can inspect setup and prepare a change set.'
          )}
        />
        <div className="grid gap-3 md:grid-cols-3">
          {[
            t(
              'adminGuides.ask.prompt1',
              'What is still missing before this instance is ready for users?'
            ),
            t(
              'adminGuides.ask.prompt2',
              'Review the current user types, onboarding questions, docs, and resources.'
            ),
            t(
              'adminGuides.ask.prompt3',
              'Prepare changes for review: set the assistant tone and default language.'
            ),
          ].map((prompt) => (
            <div
              key={prompt}
              className="rounded-lg border border-border bg-surface-raised p-4 text-sm leading-6 text-text-secondary"
            >
              {prompt}
            </div>
          ))}
        </div>
      </section>
    </PageShell>
  );
}

function GuideLinkCard({ card }: { card: GuideCard }) {
  return (
    <Link
      to={card.to ?? '/admin/setup'}
      className="card card-sm bg-surface-raised card-interactive group flex min-h-[14rem] flex-col gap-4"
    >
      <GuideCardContent card={card} />
      <div className="mt-auto inline-flex items-center gap-1 text-xs font-medium text-accent">
        <span>{card.linkLabel}</span>
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

function GuideInfoCard({ card }: { card: GuideCard }) {
  return (
    <article className="rounded-lg border border-border bg-surface-raised p-4">
      <GuideCardContent card={card} />
    </article>
  );
}

function GuideCardContent({ card }: { card: GuideCard }) {
  return (
    <>
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
          {card.icon}
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text">{card.title}</h3>
          <p className="mt-1 text-xs leading-5 text-text-secondary">
            {card.body}
          </p>
        </div>
      </div>
      <ul className="space-y-2">
        {card.details.map((detail) => (
          <li
            key={detail}
            className="flex items-start gap-2 text-xs leading-5 text-text-muted"
          >
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
            <span>{detail}</span>
          </li>
        ))}
      </ul>
    </>
  );
}
