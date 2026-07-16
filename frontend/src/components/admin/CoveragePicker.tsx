import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, Globe, X } from 'lucide-react';
import { Badge, SelectField } from '../ui';

export type CoverageLevel = '' | 'country' | 'subregion' | 'region' | 'global';

/** Coverage taxonomy returned by GET /admin/regions. */
export interface RegionData {
  countries: {
    level: 'country';
    code: string;
    name: string;
    subregion_code: string | null;
    subregion_name: string | null;
    region_code: string | null;
    region_name: string | null;
  }[];
  subregions: {
    level: 'subregion';
    code: string;
    name: string;
    region_code: string | null;
    region_name: string | null;
  }[];
  regions: { level: 'region'; code: string; name: string }[];
}

export interface CoverageValue {
  scope_level: CoverageLevel;
  scope_code: string;
}

type SelectableLevel = Exclude<CoverageLevel, '' | 'global'>;

interface CoverageOption {
  level: SelectableLevel;
  code: string;
  name: string;
}

interface Props {
  data: RegionData | null;
  value: CoverageValue;
  onChange: (value: CoverageValue) => void;
  label?: string;
  description?: string;
}

function coverageOptionKey(option: CoverageOption): string {
  return `${option.level}:${option.code}`;
}

function optionsForLevel(
  level: CoverageLevel,
  query: string,
  data: RegionData | null
): CoverageOption[] {
  if (!data || !level || level === 'global') return [];

  const normalizedQuery = query.trim().toLocaleLowerCase();
  const source =
    level === 'country'
      ? data.countries
      : level === 'subregion'
        ? data.subregions
        : data.regions;

  return source
    .map((entry) => {
      const normalizedCode = entry.code.toLocaleLowerCase();
      const normalizedName = entry.name.toLocaleLowerCase();
      let score = -1;
      if (!normalizedQuery) score = 4;
      else if (normalizedCode === normalizedQuery) score = 0;
      else if (normalizedCode.startsWith(normalizedQuery)) score = 1;
      else if (normalizedName.startsWith(normalizedQuery)) score = 2;
      else if (normalizedName.includes(normalizedQuery)) score = 3;
      return {
        option: { level, code: entry.code, name: entry.name },
        score,
      };
    })
    .filter(({ score }) => score >= 0)
    .sort(
      (left, right) =>
        left.score - right.score ||
        left.option.name.localeCompare(right.option.name)
    )
    .slice(0, 40)
    .map(({ option }) => option);
}

function selectedOption(
  value: CoverageValue,
  data: RegionData | null
): CoverageOption | null {
  if (!data || !value.scope_level || value.scope_level === 'global') {
    return null;
  }
  const options = optionsForLevel(value.scope_level, value.scope_code, data);
  return options.find((option) => option.code === value.scope_code) ?? null;
}

export function CoveragePicker({
  data,
  value,
  onChange,
  label,
  description,
}: Props) {
  const { t } = useTranslation();
  const listboxId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(false);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const committedOption = selectedOption(value, data);
  const committedLabel =
    value.scope_level === 'global'
      ? t('adminResources.level.global', 'Global')
      : committedOption
        ? `${committedOption.name} (${committedOption.code})`
        : value.scope_code;
  const options = useMemo(
    () => (editing ? optionsForLevel(value.scope_level, query, data) : []),
    [data, editing, query, value.scope_level]
  );

  useEffect(() => {
    setHighlightedIndex(0);
  }, [query, value.scope_level]);

  const revert = () => {
    setEditing(false);
    setOpen(false);
    setQuery('');
  };

  useEffect(() => {
    if (!open) return;
    const onDocumentMouseDown = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        revert();
      }
    };
    document.addEventListener('mousedown', onDocumentMouseDown);
    return () => document.removeEventListener('mousedown', onDocumentMouseDown);
  }, [open]);

  const commit = (option: CoverageOption) => {
    onChange({ scope_level: option.level, scope_code: option.code });
    revert();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setHighlightedIndex((index) =>
        Math.min(index + 1, Math.max(options.length - 1, 0))
      );
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlightedIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter' && open && options[highlightedIndex]) {
      event.preventDefault();
      commit(options[highlightedIndex]);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      revert();
    }
  };

  const searchable = Boolean(
    value.scope_level && value.scope_level !== 'global'
  );
  const taxonomyAvailable = data !== null;
  const inputValue = taxonomyAvailable
    ? editing
      ? query
      : committedLabel
    : value.scope_code;

  return (
    <div className="flex flex-col gap-2" ref={containerRef}>
      {label && <span className="text-sm font-medium text-text">{label}</span>}
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label={t('adminResources.scopeLevel', 'Coverage level')}
          value={value.scope_level}
          onChange={(event) => {
            const level = event.target.value as CoverageLevel;
            onChange({ scope_level: level, scope_code: '' });
            revert();
          }}
        >
          <option value="">—</option>
          <option value="country">
            {t('adminResources.level.country', 'Country')}
          </option>
          <option value="subregion">
            {t('adminResources.level.subregion', 'Subregion')}
          </option>
          <option value="region">
            {t('adminResources.level.region', 'Region')}
          </option>
          <option value="global">
            {t('adminResources.level.global', 'Global')}
          </option>
        </SelectField>

        <div className="flex flex-col gap-2">
          <label
            className="text-sm font-medium text-text"
            htmlFor={`${listboxId}-input`}
          >
            {t('adminResources.scopeCode', 'Coverage code')}
          </label>
          <div className="relative">
            <span className="input-container flex min-h-10 items-center gap-2 px-3">
              <Globe
                className="h-4 w-4 shrink-0 text-text-muted"
                aria-hidden="true"
              />
              <input
                id={`${listboxId}-input`}
                className="input-field text-sm"
                type="text"
                role={taxonomyAvailable ? 'combobox' : undefined}
                aria-expanded={taxonomyAvailable ? open : undefined}
                aria-autocomplete={taxonomyAvailable ? 'list' : undefined}
                aria-controls={
                  taxonomyAvailable && open ? listboxId : undefined
                }
                aria-activedescendant={
                  open && options[highlightedIndex]
                    ? `${listboxId}-${highlightedIndex}`
                    : undefined
                }
                disabled={!searchable}
                value={inputValue}
                placeholder={
                  searchable
                    ? t(
                        'adminResources.coverageCodePlaceholder',
                        'Search by name or code…'
                      )
                    : t(
                        'adminResources.coverageLevelFirst',
                        'Choose a coverage level first'
                      )
                }
                onFocus={() => {
                  if (!searchable || !taxonomyAvailable) return;
                  setEditing(true);
                  setQuery('');
                  setOpen(true);
                }}
                onChange={(event) => {
                  if (!taxonomyAvailable) {
                    onChange({ ...value, scope_code: event.target.value });
                    return;
                  }
                  setEditing(true);
                  setQuery(event.target.value);
                  setOpen(true);
                }}
                onKeyDown={onKeyDown}
                onBlur={revert}
              />
              {value.scope_code && !editing && (
                <button
                  type="button"
                  aria-label={t(
                    'adminResources.coverageClear',
                    'Clear coverage code'
                  )}
                  className="shrink-0 text-text-muted transition-colors hover:text-text"
                  onClick={() => {
                    onChange({ ...value, scope_code: '' });
                  }}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
              {taxonomyAvailable && (
                <ChevronDown
                  className={`h-4 w-4 shrink-0 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`}
                  aria-hidden="true"
                />
              )}
            </span>

            {open && options.length > 0 && (
              <ul
                id={listboxId}
                role="listbox"
                className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-y-auto rounded-xl border border-border bg-surface-raised shadow-lg animate-fade-in-scale"
              >
                {options.map((option, index) => {
                  const selected = value.scope_code === option.code;
                  return (
                    <li key={coverageOptionKey(option)}>
                      <button
                        id={`${listboxId}-${index}`}
                        type="button"
                        role="option"
                        aria-selected={selected}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          commit(option);
                        }}
                        onMouseEnter={() => setHighlightedIndex(index)}
                        className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
                          index === highlightedIndex
                            ? 'bg-surface-overlay text-text'
                            : 'text-text-secondary hover:bg-surface-overlay hover:text-text'
                        }`}
                      >
                        <Badge
                          tone={
                            option.level === 'country' ? 'accent' : 'neutral'
                          }
                        >
                          {t(
                            `adminResources.level.${option.level}`,
                            option.level
                          )}
                        </Badge>
                        <span className="min-w-0 flex-1 truncate">
                          {option.name}
                        </span>
                        <span className="shrink-0 font-mono text-xs text-text-muted">
                          {option.code}
                        </span>
                        {selected && (
                          <Check
                            className="h-4 w-4 shrink-0 text-accent"
                            aria-hidden="true"
                          />
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>
      {!data && searchable && (
        <p className="text-xs text-text-muted" role="status">
          {t(
            'adminResources.regionDirectoryUnavailable',
            'Region directory unavailable. Enter a code manually.'
          )}
        </p>
      )}
      {description && <p className="text-xs text-text-muted">{description}</p>}
    </div>
  );
}
