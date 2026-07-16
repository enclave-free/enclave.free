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

const RESOURCE_TYPES = [
  'lawyer',
  'ngo',
  'un_body',
  'clinic',
  'shelter',
  'financial',
  'hotline',
  'other',
] as const;
const CONTACT_KEYS = [
  'phone',
  'email',
  'url',
  'secure_channel',
  'address',
  'notes',
] as const;

type ContactKey = (typeof CONTACT_KEYS)[number];

interface ResourceContact {
  phone?: string;
  email?: string;
  url?: string;
  secure_channel?: string;
  address?: string;
  notes?: string;
}

interface Resource {
  resource_id: string;
  name: string | null;
  resource_type: string | null;
  description: string | null;
  contact: ResourceContact;
  languages: string[];
  scope_level: CoverageLevel | null;
  scope_code: string | null;
  coverage: string | null;
  help_types: string[];
  status: 'pending' | 'ready' | 'archived';
  missing_fields: string[];
  verified_at: string | null;
  vetted_by: string | null;
  source_note: string | null;
  display_order: number;
}

interface HelpType {
  key: string;
  label: string;
  description?: string | null;
}

interface FormState {
  resource_id: string;
  name: string;
  resource_type: string;
  description: string;
  scope_level: CoverageLevel;
  scope_code: string;
  help_types: string[];
  languages: string;
  contact: ResourceContact;
  verified: boolean;
  vetted_by: string;
  source_note: string;
  archived: boolean;
}

const EMPTY_FORM: FormState = {
  resource_id: '',
  name: '',
  resource_type: '',
  description: '',
  scope_level: '',
  scope_code: '',
  help_types: [],
  languages: '',
  contact: {},
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
    resource_type: resource.resource_type ?? '',
    description: resource.description ?? '',
    scope_level: resource.scope_level ?? '',
    scope_code: resource.scope_code ?? '',
    help_types: resource.help_types ?? [],
    languages: (resource.languages ?? []).join(', '),
    contact: { ...resource.contact },
    verified: Boolean(resource.verified_at),
    vetted_by: resource.vetted_by ?? '',
    source_note: resource.source_note ?? '',
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
  const [helpTypes, setHelpTypes] = useState<HelpType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<Resource | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Resource | null>(null);
  const [regionData, setRegionData] = useState<RegionData | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [resResources, resHelpTypes, resRegions] = await Promise.all([
        adminFetch('/admin/resources'),
        adminFetch('/admin/help-types'),
        adminFetch('/admin/regions'),
      ]);
      if (!resResources.ok) throw new Error('Failed to load resources');
      if (!resHelpTypes.ok) throw new Error('Failed to load help types');
      const resourcesData = await resResources.json();
      const helpTypesData = await resHelpTypes.json();
      setResources(resourcesData.resources ?? []);
      setHelpTypes(helpTypesData.help_types ?? []);
      // Region taxonomy is best-effort; the coverage picker degrades gracefully.
      if (resRegions.ok) setRegionData((await resRegions.json()) as RegionData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load directory');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Refresh the table when the assistant applies a resource change set while
  // this page is open, so chat-driven edits show up without a manual reload.
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

  const helpTypeLabels = useMemo(() => {
    const map = new Map<string, string>();
    helpTypes.forEach((h) => map.set(h.key, h.label));
    return map;
  }, [helpTypes]);

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

  const toggleHelpType = (key: string) => {
    setForm((prev) => ({
      ...prev,
      help_types: prev.help_types.includes(key)
        ? prev.help_types.filter((k) => k !== key)
        : [...prev.help_types, key],
    }));
  };

  const setContactField = (key: ContactKey, value: string) => {
    setForm((prev) => ({
      ...prev,
      contact: { ...prev.contact, [key]: value },
    }));
  };

  const buildBody = () => {
    const contact: ResourceContact = {};
    CONTACT_KEYS.forEach((key) => {
      const value = (form.contact[key] ?? '').trim();
      if (value) contact[key] = value;
    });
    const languages = form.languages
      .split(',')
      .map((l) => l.trim())
      .filter(Boolean);
    const body: Record<string, unknown> = {
      name: form.name.trim() || null,
      resource_type: form.resource_type || null,
      description: form.description.trim() || null,
      scope_level: form.scope_level || null,
      scope_code:
        form.scope_level === 'global' ? null : form.scope_code.trim() || null,
      help_types: form.help_types,
      languages,
      contact,
      verified: form.verified,
      vetted_by: form.vetted_by.trim() || null,
      source_note: form.source_note.trim() || null,
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
        throw new Error(detail?.detail ?? 'Failed to save resource');
      }
      await fetchData();
      closeForm();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Failed to save resource');
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
      if (!response.ok) throw new Error('Failed to delete resource');
      await fetchData();
      setDeleteTarget(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete resource');
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
      ) : (
        <div className="flex flex-col gap-3">
          {resources.map((resource) => (
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
                    {resource.verified_at && (
                      <Badge tone="info">
                        <ShieldCheck className="mr-1 inline h-3 w-3" />
                        {t('adminResources.verified', 'verified')}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 text-sm text-text-secondary">
                    {[resource.resource_type, resource.coverage]
                      .filter(Boolean)
                      .join(' · ')}
                  </div>
                  {resource.help_types.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {resource.help_types.map((key) => (
                        <Badge key={key} tone="neutral">
                          {helpTypeLabels.get(key) ?? key}
                        </Badge>
                      ))}
                    </div>
                  )}
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
                placeholder="e.g. Central America Human Rights Counsel"
              />

              <div className="grid gap-4 sm:grid-cols-2">
                <SelectField
                  label={t('adminResources.type', 'Resource type')}
                  value={form.resource_type}
                  onChange={(e) =>
                    setForm({ ...form, resource_type: e.target.value })
                  }
                >
                  <option value="">—</option>
                  {RESOURCE_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
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
                  placeholder="es, en"
                />
              </div>

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

              <CoveragePicker
                data={regionData}
                value={{
                  scope_level: form.scope_level,
                  scope_code: form.scope_code,
                }}
                onChange={(v) =>
                  setForm({
                    ...form,
                    scope_level: v.scope_level,
                    scope_code: v.scope_code,
                  })
                }
                label={t('adminResources.coverage', 'Coverage')}
                description={t(
                  'adminResources.coverageHint',
                  'Choose a coverage level, then search for its name or code.'
                )}
              />

              <div>
                <div className="mb-1 text-sm font-medium text-text">
                  {t('adminResources.helpTypes', 'Types of help')}
                </div>
                <div className="flex flex-wrap gap-2">
                  {helpTypes.map((helpType) => {
                    const active = form.help_types.includes(helpType.key);
                    return (
                      <button
                        key={helpType.key}
                        type="button"
                        onClick={() => toggleHelpType(helpType.key)}
                        aria-pressed={active}
                        className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                          active
                            ? 'border-accent bg-accent/10 text-accent'
                            : 'border-border text-text-secondary hover:border-accent/50'
                        }`}
                      >
                        {helpType.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <div className="mb-1 text-sm font-medium text-text">
                  {t('adminResources.contact', 'Contact methods')}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {CONTACT_KEYS.map((key) => (
                    <TextField
                      key={key}
                      label={key}
                      value={form.contact[key] ?? ''}
                      onChange={(e) => setContactField(key, e.target.value)}
                    />
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
                  {t(
                    'adminResources.markVerified',
                    'Mark as verified (ranks first)'
                  )}
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
