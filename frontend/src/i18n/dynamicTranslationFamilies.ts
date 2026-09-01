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

const readinessItemKeys = Object.keys(deploymentReadinessStatuses);

const readinessStatusKeys = Object.entries(deploymentReadinessStatuses).flatMap(
  ([item, statuses]) =>
    statuses.flatMap((status) => [
      `adminDeployment.readiness.${item}.status.${status}.summary`,
      `adminDeployment.readiness.${item}.status.${status}.nextAction`,
    ])
);

export const dynamicTranslationFamilies = [
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
