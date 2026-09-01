import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  LifeBuoy,
  ShieldCheck,
  X,
} from 'lucide-react';
import {
  Badge,
  Button,
  Callout,
  Card,
  IconButton,
  PageShell,
  SectionHeader,
  SelectField,
  TextField,
  Textarea,
} from '../components/ui';
import { adminFetch, ADMIN_RESOURCES_CHANGED_EVENT } from '../utils/adminApi';
import {
  CoveragePicker,
  type CoverageLevel,
  type RegionData,
} from '../components/admin/CoveragePicker';

const RESOURCE_KINDS = [
  'person',
  'organization',
  'product',
  'service',
  'method',
  'reference',
  'other',
] as const;
const POINTER_TYPES = [
  'email',
  'phone',
  'url',
  'address',
  'secure_channel',
  'identifier',
  'other',
] as const;

type ResourceKind = (typeof RESOURCE_KINDS)[number];
type PointerType = (typeof POINTER_TYPES)[number];

interface ResourcePointer {
  type: PointerType;
  value: string;
  label?: string | null;
}

interface ResourceRegion {
  level: Exclude<CoverageLevel, ''>;
  code: string | null;
}

interface ResourceProvenance {
  verified_at?: string | null;
  vetted_by?: string | null;
  source_note?: string | null;
}

interface Resource {
  resource_id: string;
  name: string | null;
  kind: ResourceKind | null;
  tags: string[];
  pointers: ResourcePointer[];
  regions: ResourceRegion[];
  provenance: ResourceProvenance;
  description: string | null;
  languages: string[];
  status: 'pending' | 'ready' | 'archived';
  missing_fields: string[];
  display_order: number;
}

function parseRegionData(value: unknown): RegionData | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<RegionData>;
  if (
    !Array.isArray(candidate.countries) ||
    !Array.isArray(candidate.subregions) ||
    !Array.isArray(candidate.regions)
  ) {
    return null;
  }

  const isNullableString = (field: unknown) =>
    field === null || typeof field === 'string';
  const countriesValid = candidate.countries.every(
    (entry) =>
      entry?.level === 'country' &&
      typeof entry.code === 'string' &&
      typeof entry.name === 'string' &&
      isNullableString(entry.subregion_code) &&
      isNullableString(entry.subregion_name) &&
      isNullableString(entry.region_code) &&
      isNullableString(entry.region_name)
  );
  const subregionsValid = candidate.subregions.every(
    (entry) =>
      entry?.level === 'subregion' &&
      typeof entry.code === 'string' &&
      typeof entry.name === 'string' &&
      isNullableString(entry.region_code) &&
      isNullableString(entry.region_name)
  );
  const regionsValid = candidate.regions.every(
    (entry) =>
      entry?.level === 'region' &&
      typeof entry.code === 'string' &&
      typeof entry.name === 'string'
  );

  return countriesValid && subregionsValid && regionsValid
    ? (candidate as RegionData)
    : null;
}

interface FormState {
  resource_id: string;
  name: string;
  kind: ResourceKind | '';
  tags: string;
  description: string;
  pointers: ResourcePointer[];
  regions: { level: CoverageLevel; code: string }[];
  languages: string;
  display_order: string;
  verified: boolean;
  vetted_by: string;
  source_note: string;
  archived: boolean;
}

const EMPTY_FORM: FormState = {
  resource_id: '',
  name: '',
  kind: '',
  tags: '',
  description: '',
  pointers: [{ type: 'url', value: '', label: '' }],
  regions: [{ level: '', code: '' }],
  languages: '',
  display_order: '0',
  verified: false,
  vetted_by: '',
  source_note: '',
  archived: false,
};

function statusTone(
  status: Resource['status']
): 'success' | 'warning' | 'neutral' {
  if (status === 'ready') return 'success';
  if (status === 'pending') return 'warning';
  return 'neutral';
}

function resourceToForm(resource: Resource): FormState {
  return {
    resource_id: resource.resource_id,
    name: resource.name ?? '',
    kind: resource.kind ?? '',
    tags: (resource.tags ?? []).join(', '),
    description: resource.description ?? '',
    pointers:
      resource.pointers?.length > 0
        ? resource.pointers.map((pointer) => ({
            ...pointer,
            label: pointer.label ?? '',
          }))
        : [{ type: 'url', value: '', label: '' }],
    regions:
      resource.regions?.length > 0
        ? resource.regions.map((region) => ({
            level: region.level,
            code: region.code ?? '',
          }))
        : [{ level: '', code: '' }],
    languages: (resource.languages ?? []).join(', '),
    display_order: String(resource.display_order ?? 0),
    verified: Boolean(resource.provenance?.verified_at),
    vetted_by: resource.provenance?.vetted_by ?? '',
    source_note: resource.provenance?.source_note ?? '',
    archived: resource.status === 'archived',
  };
}

export function AdminResourcesDirectory({
  embedded = false,
}: {
  embedded?: boolean;
} = {}) {
  const { t } = useTranslation();
  const [resources, setResources] = useState<Resource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<Resource | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Resource | null>(null);
  const [regionData, setRegionData] = useState<RegionData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const regionDataPromise = adminFetch('/admin/regions')
        .then(async (response) =>
          response.ok ? parseRegionData(await response.json()) : null
        )
        .catch(() => null);
      const [resResources, nextRegionData] = await Promise.all([
        adminFetch('/admin/resources'),
        regionDataPromise,
      ]);
      if (!resResources.ok) {
        throw new Error(
          t('adminResources.loadError', 'Failed to load resources')
        );
      }
      const resourcesData = await resResources.json();
      setResources(resourcesData.resources ?? []);
      // Region taxonomy is best-effort; the coverage picker degrades gracefully.
      setRegionData(nextRegionData);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t('adminResources.loadDirectoryError', 'Failed to load directory')
      );
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const visibleResources = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase();
    if (!query) return resources;
    return resources.filter((resource) =>
      [
        resource.resource_id,
        resource.name,
        resource.kind,
        resource.description,
        ...(resource.tags ?? []),
        ...(resource.pointers ?? []).flatMap((pointer) => [
          pointer.type,
          pointer.label,
          pointer.value,
        ]),
      ].some((value) =>
        String(value ?? '')
          .toLocaleLowerCase()
          .includes(query)
      )
    );
  }, [resources, searchQuery]);

  // Refresh the table after a resource-directory mutation while this page is
  // open, so another admin surface can keep the view current.
  useEffect(() => {
    const handleResourcesChanged = () => {
      void fetchData();
    };
    window.addEventListener(
      ADMIN_RESOURCES_CHANGED_EVENT,
      handleResourcesChanged
    );
    return () =>
      window.removeEventListener(
        ADMIN_RESOURCES_CHANGED_EVENT,
        handleResourcesChanged
      );
  }, [fetchData]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setShowForm(true);
  };

  const openEdit = (resource: Resource) => {
    setEditing(resource);
    setForm(resourceToForm(resource));
    setFormError(null);
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
    setFormError(null);
  };

  const setPointer = (
    index: number,
    field: keyof ResourcePointer,
    value: string
  ) => {
    setForm((prev) => ({
      ...prev,
      pointers: prev.pointers.map((pointer, pointerIndex) =>
        pointerIndex === index ? { ...pointer, [field]: value } : pointer
      ),
    }));
  };

  const removePointer = (index: number) => {
    setForm((prev) => ({
      ...prev,
      pointers: prev.pointers.filter(
        (_, pointerIndex) => pointerIndex !== index
      ),
    }));
  };

  const setRegion = (
    index: number,
    value: { scope_level: CoverageLevel; scope_code: string }
  ) => {
    setForm((prev) => ({
      ...prev,
      regions: prev.regions.map((region, regionIndex) =>
        regionIndex === index
          ? { level: value.scope_level, code: value.scope_code }
          : region
      ),
    }));
  };

  const buildBody = () => {
    const languages = form.languages
      .split(',')
      .map((l) => l.trim())
      .filter(Boolean);
    const body: Record<string, unknown> = {
      name: form.name.trim() || null,
      kind: form.kind || null,
      tags: form.tags
        .split(',')
        .map((tag) => tag.trim().toLocaleLowerCase())
        .filter(Boolean),
      description: form.description.trim() || null,
      pointers: form.pointers
        .map((pointer) => ({
          type: pointer.type,
          value: pointer.value.trim(),
          label: pointer.label?.trim() || null,
        }))
        .filter((pointer) => pointer.value),
      regions: form.regions
        .filter((region) => region.level)
        .map((region) => ({
          level: region.level,
          code: region.level === 'global' ? null : region.code.trim() || null,
        })),
      languages,
      display_order: Number.parseInt(form.display_order, 10) || 0,
      verified: form.verified,
      provenance: {
        vetted_by: form.vetted_by.trim() || null,
        source_note: form.source_note.trim() || null,
      },
      archived: form.archived,
    };
    if (!editing && form.resource_id.trim()) {
      body.resource_id = form.resource_id.trim();
    }
    return body;
  };

  const handleSubmit = async () => {
    setSaving(true);
    setFormError(null);
    try {
      const body = buildBody();
      const endpoint = editing
        ? `/admin/resources/${editing.resource_id}`
        : '/admin/resources';
      const method = editing ? 'PUT' : 'POST';
      const response = await adminFetch(endpoint, {
        method,
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(
          detail?.detail ??
            t('adminResources.saveError', 'Failed to save resource')
        );
      }
      await fetchData();
      closeForm();
    } catch (e) {
      setFormError(
        e instanceof Error
          ? e.message
          : t('adminResources.saveError', 'Failed to save resource')
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setSaving(true);
    try {
      const response = await adminFetch(
        `/admin/resources/${deleteTarget.resource_id}`,
        { method: 'DELETE' }
      );
      if (!response.ok) {
        throw new Error(
          t('adminResources.deleteError', 'Failed to delete resource')
        );
      }
      await fetchData();
      setDeleteTarget(null);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : t('adminResources.deleteError', 'Failed to delete resource')
      );
    } finally {
      setSaving(false);
    }
  };

  const addButton = (
    <Button
      variant="primary"
      size="sm"
      onClick={openCreate}
      leadingIcon={<Plus className="h-4 w-4" />}
    >
      {t('adminResources.add', 'Add resource')}
    </Button>
  );

  const body = (
    <>
      {error && <Callout tone="error">{error}</Callout>}

      <TextField
        label={t('adminResources.search', 'Search resources')}
        value={searchQuery}
        onChange={(event) => setSearchQuery(event.target.value)}
        placeholder={t(
          'adminResources.searchPlaceholder',
          'Name, kind, tag, pointer, or description'
        )}
      />

      {loading ? (
        <div className="flex items-center justify-center py-16 text-text-secondary">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : resources.length === 0 ? (
        <Card className="py-12 text-center text-text-secondary">
          {t(
            'adminResources.empty',
            'No resources yet. Add one manually when you have a vetted referral.'
          )}
        </Card>
      ) : visibleResources.length === 0 ? (
        <Card className="py-12 text-center text-text-secondary">
          {t(
            'adminResources.noSearchResults',
            'No resources match this search.'
          )}
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {visibleResources.map((resource) => (
            <Card
              key={resource.resource_id}
              className="flex flex-col gap-2 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-text">
                      {resource.name || resource.resource_id}
                    </span>
                    <Badge tone={statusTone(resource.status)}>
                      {resource.status}
                    </Badge>
                    {resource.provenance?.verified_at && (
                      <Badge tone="info">
                        <ShieldCheck className="mr-1 inline h-3 w-3" />
                        {t('adminResources.verified', 'verified')}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 text-sm text-text-secondary">
                    {[
                      resource.kind,
                      (resource.regions ?? [])
                        .map((region) =>
                          region.level === 'global'
                            ? 'Global'
                            : `${region.level}: ${region.code}`
                        )
                        .join(', '),
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </div>
                  {resource.tags.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {resource.tags.map((tag) => (
                        <Badge key={tag} tone="neutral">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {resource.pointers.length > 0 && (
                    <div className="mt-1 text-xs text-text-secondary">
                      {resource.pointers
                        .map(
                          (pointer) =>
                            `${pointer.label || pointer.type}: ${pointer.value}`
                        )
                        .join(' · ')}
                    </div>
                  )}
                  <div className="mt-1 text-xs text-text-secondary">
                    {t('adminResources.order', 'Order')}:{' '}
                    {resource.display_order}
                  </div>
                  {resource.status === 'pending' &&
                    resource.missing_fields.length > 0 && (
                      <div className="mt-1 text-xs text-warning">
                        {t('adminResources.missing', 'Missing to go live')}:{' '}
                        {resource.missing_fields.join(', ')}
                      </div>
                    )}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <IconButton
                    label={t('common.edit', 'Edit')}
                    onClick={() => openEdit(resource)}
                  >
                    <Pencil className="h-4 w-4" />
                  </IconButton>
                  <IconButton
                    label={t('common.delete', 'Delete')}
                    onClick={() => setDeleteTarget(resource)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </IconButton>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {showForm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="resource-dialog-title"
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4"
        >
          <Card className="my-8 w-full max-w-2xl">
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <h2
                id="resource-dialog-title"
                className="text-base font-semibold text-text"
              >
                {editing
                  ? t('adminResources.editTitle', 'Edit resource')
                  : t('adminResources.addTitle', 'Add resource')}
              </h2>
              <IconButton
                label={t('common.close', 'Close')}
                onClick={closeForm}
              >
                <X className="h-4 w-4" />
              </IconButton>
            </div>
            <div className="flex flex-col gap-4 px-5 py-4">
              {formError && <Callout tone="error">{formError}</Callout>}

              <TextField
                label={t('adminResources.name', 'Name')}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t(
                  'adminResources.namePlaceholder',
                  'e.g. Central America Human Rights Counsel'
                )}
              />

              <div className="grid gap-4 sm:grid-cols-2">
                <SelectField
                  label={t('adminResources.kind', 'Kind')}
                  value={form.kind}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      kind: e.target.value as ResourceKind | '',
                    })
                  }
                >
                  <option value="">—</option>
                  {RESOURCE_KINDS.map((kind) => (
                    <option key={kind} value={kind}>
                      {kind}
                    </option>
                  ))}
                </SelectField>
                <TextField
                  label={t(
                    'adminResources.languages',
                    'Languages (comma-separated ISO codes)'
                  )}
                  value={form.languages}
                  onChange={(e) =>
                    setForm({ ...form, languages: e.target.value })
                  }
                  placeholder={t(
                    'adminResources.languagesPlaceholder',
                    'es, en'
                  )}
                />
              </div>

              <TextField
                label={t('adminResources.tags', 'Tags (comma-separated)')}
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                placeholder={t(
                  'adminResources.tagsPlaceholder',
                  'bitcoin, education, local'
                )}
              />

              <TextField
                type="number"
                label={t('adminResources.displayOrder', 'Display order')}
                value={form.display_order}
                onChange={(event) =>
                  setForm({ ...form, display_order: event.target.value })
                }
                description={t(
                  'adminResources.displayOrderHint',
                  'Lower numbers appear first after relevance and verification.'
                )}
              />

              <Textarea
                label={t('adminResources.description', 'Description')}
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                rows={2}
                description={t(
                  'adminResources.descriptionHint',
                  'What the assistant should tell the person about this resource.'
                )}
              />

              <div>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-text">
                    {t('adminResources.regions', 'Regions')}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setForm({
                        ...form,
                        regions: [...form.regions, { level: '', code: '' }],
                      })
                    }
                  >
                    {t('adminResources.addRegion', 'Add region')}
                  </Button>
                </div>
                <div className="flex flex-col gap-3">
                  {form.regions.map((region, index) => (
                    <div
                      key={index}
                      className="rounded-lg border border-border p-3"
                    >
                      <CoveragePicker
                        data={regionData}
                        value={{
                          scope_level: region.level,
                          scope_code: region.code,
                        }}
                        onChange={(value) => setRegion(index, value)}
                        label={t(
                          'adminResources.regionNumber',
                          'Region {{number}}',
                          {
                            number: index + 1,
                          }
                        )}
                        description={t(
                          'adminResources.coverageHint',
                          'Choose a coverage level, then search for its name or code.'
                        )}
                      />
                      {form.regions.length > 1 && (
                        <div className="mt-2 flex justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setForm({
                                ...form,
                                regions: form.regions.filter(
                                  (_, regionIndex) => regionIndex !== index
                                ),
                              })
                            }
                          >
                            {t('adminResources.removeRegion', 'Remove region')}
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-text">
                    {t('adminResources.pointers', 'Pointers')}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setForm({
                        ...form,
                        pointers: [
                          ...form.pointers,
                          { type: 'url', value: '', label: '' },
                        ],
                      })
                    }
                  >
                    {t('adminResources.addPointer', 'Add pointer')}
                  </Button>
                </div>
                <div className="flex flex-col gap-3">
                  {form.pointers.map((pointer, index) => (
                    <div
                      key={index}
                      className="grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-3"
                    >
                      <SelectField
                        label={t(
                          'adminResources.pointerType',
                          'Pointer {{number}} type',
                          {
                            number: index + 1,
                          }
                        )}
                        value={pointer.type}
                        onChange={(event) =>
                          setPointer(index, 'type', event.target.value)
                        }
                      >
                        {POINTER_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {type}
                          </option>
                        ))}
                      </SelectField>
                      <TextField
                        label={t(
                          'adminResources.pointerValue',
                          'Pointer {{number}} value',
                          {
                            number: index + 1,
                          }
                        )}
                        value={pointer.value}
                        onChange={(event) =>
                          setPointer(index, 'value', event.target.value)
                        }
                      />
                      <TextField
                        label={t(
                          'adminResources.pointerLabel',
                          'Pointer {{number}} label',
                          {
                            number: index + 1,
                          }
                        )}
                        value={pointer.label ?? ''}
                        onChange={(event) =>
                          setPointer(index, 'label', event.target.value)
                        }
                      />
                      {form.pointers.length > 1 && (
                        <div className="sm:col-span-3 flex justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removePointer(index)}
                          >
                            {t(
                              'adminResources.removePointer',
                              'Remove pointer'
                            )}
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <TextField
                  label={t('adminResources.vettedBy', 'Vetted by')}
                  value={form.vetted_by}
                  onChange={(e) =>
                    setForm({ ...form, vetted_by: e.target.value })
                  }
                />
                <TextField
                  label={t('adminResources.sourceNote', 'Source note')}
                  value={form.source_note}
                  onChange={(e) =>
                    setForm({ ...form, source_note: e.target.value })
                  }
                />
              </div>

              <div className="flex flex-wrap gap-6">
                <label className="flex items-center gap-2 text-sm text-text">
                  <input
                    type="checkbox"
                    checked={form.verified}
                    onChange={(e) =>
                      setForm({ ...form, verified: e.target.checked })
                    }
                  />
                  {t('adminResources.markVerified', 'Mark as verified')}
                </label>
                <label className="flex items-center gap-2 text-sm text-text">
                  <input
                    type="checkbox"
                    checked={form.archived}
                    onChange={(e) =>
                      setForm({ ...form, archived: e.target.checked })
                    }
                  />
                  {t('adminResources.archive', 'Archive (hide from end users)')}
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
              <Button variant="ghost" onClick={closeForm} disabled={saving}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button
                variant="primary"
                onClick={handleSubmit}
                disabled={saving}
              >
                {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                {t('common.save', 'Save')}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {deleteTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-resource-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        >
          <Card className="w-full max-w-md p-5">
            <h2
              id="delete-resource-dialog-title"
              className="text-base font-semibold text-text"
            >
              {t('adminResources.deleteTitle', 'Delete resource?')}
            </h2>
            <p className="mt-2 text-sm text-text-secondary">
              {t(
                'adminResources.deleteBody',
                'This removes the directory entry for {{name}}',
                { name: deleteTarget.name || deleteTarget.resource_id }
              )}
              .
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setDeleteTarget(null)}
                disabled={saving}
              >
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button variant="danger" onClick={handleDelete} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                {t('common.delete', 'Delete')}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </>
  );

  if (embedded) {
    return (
      <div className="flex w-full flex-col gap-6">
        <div className="flex items-center justify-end">{addButton}</div>
        {body}
      </div>
    );
  }

  return (
    <PageShell
      width="lg"
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
            title={
              <span className="inline-flex items-center gap-2">
                <LifeBuoy className="h-5 w-5" />
                {t('adminResources.title', 'Resource Directory')}
              </span>
            }
            description={t(
              'adminResources.subtitle',
              'Manually maintain vetted referral resources the assistant can mention when a conversation escalates. Only "ready" resources are shown to end users.'
            )}
            actions={addButton}
          />
        </div>
      }
    >
      {body}
    </PageShell>
  );
}
