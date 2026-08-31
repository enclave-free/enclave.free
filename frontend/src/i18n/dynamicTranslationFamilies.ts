import type { FieldType } from '../types/onboarding';
import type { DynamicTranslationFamily } from './localizationContract';

export const localizedFieldTypes = [
  'text',
  'email',
  'number',
  'textarea',
  'select',
  'checkbox',
  'date',
  'url',
] as const satisfies readonly FieldType[];

export const reachoutModes = ['feedback', 'help', 'support'] as const;
export type ReachoutMode = (typeof reachoutModes)[number];

export const localizedCoverageLevels = [
  'country',
  'subregion',
  'region',
] as const;

const adminGuideQuickStepIndexes = [0, 1, 2, 3, 4] as const;
const adminGuideSafetyItemIndexes = [0, 1, 2, 3, 4] as const;
const readinessItemKeys = [
  'deployment_settings_validation',
  'verifiable_inference',
  'lifecycle_readiness',
  'deployment_surface_acknowledgements',
  'backup_restore_drill',
  'restart_required',
  'sage_runtime_env',
  'core_backend_runtime_env',
] as const;

export const deploymentReadinessStatuses = {
  deployment_settings_validation: ['invalid', 'warnings', 'valid'],
  verifiable_inference: ['current', 'deferred_missing'],
  lifecycle_readiness: ['needs_review', 'stale', 'reviewed'],
  deployment_surface_acknowledgements: [
    'acknowledged',
    'needs_acknowledgement',
  ],
  backup_restore_drill: ['operator_evidence_required'],
  restart_required: ['current', 'restart_required'],
  sage_runtime_env: [
    'not_generated',
    'matches_desired',
    'drifted',
    'current',
    'stale',
  ],
  core_backend_runtime_env: [
    'not_generated',
    'matches_desired',
    'drifted',
    'current',
    'stale',
  ],
} as const;

const readinessStatusKeys = Object.entries(deploymentReadinessStatuses).flatMap(
  ([item, statuses]) =>
    statuses.flatMap((status) => [
      `adminDeployment.readiness.${item}.status.${status}.summary`,
      `adminDeployment.readiness.${item}.status.${status}.nextAction`,
    ])
);

export const dynamicTranslationFamilies = [
  {
    name: 'Sage Conversation Activity messages',
    template: 'chat.activity.${}',
    keys: [
      'chat.activity.tool.title',
      'chat.activity.tool.attempted',
      'chat.activity.tool.retry',
      'chat.activity.tool.running',
      'chat.activity.tool.knowledgeSearch.title',
      'chat.activity.tool.webSearch.title',
      'chat.activity.tool.curatedResources.title',
      'chat.activity.tool.adminConfig.title',
      'chat.activity.tool.databaseQuery.title',
      'chat.activity.status.running',
      'chat.activity.status.succeeded',
      'chat.activity.status.failed',
      'chat.activity.status.guarded',
      'chat.activity.status.timed_out',
      'chat.activity.status.rejected',
      'chat.activity.toolSelection.title',
      'chat.activity.toolSelection.failed',
      'chat.activity.toolSelection.partialFailure',
      'chat.activity.toolSelection.noneSelected',
      'chat.activity.toolSelection.selected',
      'chat.activity.timing.modelRequest.title',
      'chat.activity.timing.modelRequest.summary',
      'chat.activity.timing.providerFirstEventWait.title',
      'chat.activity.timing.providerFirstEventWait.summary',
      'chat.activity.timing.toolExecution.title',
      'chat.activity.timing.toolExecution.summary',
      'chat.activity.timing.resourceDirectoryLookup.title',
      'chat.activity.timing.resourceDirectoryLookup.summary',
      'chat.activity.timing.retrieval.title',
      'chat.activity.timing.retrieval.summary',
      'chat.activity.timing.retryDelay.title',
      'chat.activity.timing.retryDelay.summary',
      'chat.activity.timing.totalTurn.title',
      'chat.activity.timing.totalTurn.summary',
      'chat.activity.knowledgeSearch.noResults',
      'chat.activity.knowledgeSearch.retrieved',
      'chat.activity.webSearch.prepared',
      'chat.activity.curatedResources.noAdditional',
      'chat.activity.curatedResources.noMatches',
      'chat.activity.curatedResources.returned',
      'chat.activity.adminConfig.completed',
      'chat.activity.databaseResultsRedacted',
      'chat.activity.databaseQuery.rejected',
      'chat.activity.tool.completed',
      'chat.activity.tool.guarded',
      'chat.activity.tool.failed',
      'chat.activity.tool.rejected',
      'chat.activity.tool.timedOut',
    ],
  },
  {
    name: 'Admin field type labels',
    template: 'admin.fieldTypes.${}',
    keys: localizedFieldTypes.map((type) => `admin.fieldTypes.${type}`),
  },
  {
    name: 'Admin field type descriptions',
    template: 'admin.fieldTypes.${}Desc',
    keys: localizedFieldTypes.map((type) => `admin.fieldTypes.${type}Desc`),
  },
  {
    name: 'Admin reachout mode titles',
    template: 'admin.reachout.mode.${}.title',
    keys: reachoutModes.map((mode) => `admin.reachout.mode.${mode}.title`),
  },
  {
    name: 'Admin reachout mode descriptions',
    template: 'admin.reachout.mode.${}.desc',
    keys: reachoutModes.map((mode) => `admin.reachout.mode.${mode}.desc`),
  },
  {
    name: 'User reachout open buttons',
    template: 'reachout.mode.${}.openButton',
    keys: reachoutModes.map((mode) => `reachout.mode.${mode}.openButton`),
  },
  {
    name: 'User reachout titles',
    template: 'reachout.mode.${}.title',
    keys: reachoutModes.map((mode) => `reachout.mode.${mode}.title`),
  },
  {
    name: 'User reachout descriptions',
    template: 'reachout.mode.${}.description',
    keys: reachoutModes.map((mode) => `reachout.mode.${mode}.description`),
  },
  {
    name: 'Resource coverage levels',
    template: 'adminResources.level.${}',
    keys: localizedCoverageLevels.map(
      (level) => `adminResources.level.${level}`
    ),
  },
  {
    name: 'Admin Guide quick-step titles',
    template: 'adminGuides.quickSteps.${}.title',
    keys: adminGuideQuickStepIndexes.map(
      (index) => `adminGuides.quickSteps.${index}.title`
    ),
  },
  {
    name: 'Admin Guide quick-step bodies',
    template: 'adminGuides.quickSteps.${}.body',
    keys: adminGuideQuickStepIndexes.map(
      (index) => `adminGuides.quickSteps.${index}.body`
    ),
  },
  {
    name: 'Admin Guide safety items',
    template: 'adminGuides.safety.directItems.${}',
    keys: adminGuideSafetyItemIndexes.map(
      (index) => `adminGuides.safety.directItems.${index}`
    ),
  },
  {
    name: 'Deployment Readiness labels',
    template: 'adminDeployment.readiness.${}.label',
    keys: readinessItemKeys.map(
      (item) => `adminDeployment.readiness.${item}.label`
    ),
  },
  {
    name: 'Deployment Readiness summaries',
    template: 'adminDeployment.readiness.${}.status.${}.summary',
    keys: readinessStatusKeys.filter((key) => key.endsWith('.summary')),
  },
  {
    name: 'Deployment Readiness next actions',
    template: 'adminDeployment.readiness.${}.status.${}.nextAction',
    keys: readinessStatusKeys.filter((key) => key.endsWith('.nextAction')),
  },
] as const satisfies readonly DynamicTranslationFamily[];
