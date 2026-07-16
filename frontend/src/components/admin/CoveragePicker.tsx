import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, Globe, X } from 'lucide-react';
import { Badge } from '../ui';

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
  scope_level: string;
  scope_code: string;
}

interface Option {
  level: 'country' | 'subregion' | 'region' | 'global';
  code: string; // '' for global
  name: string;
}

interface Props {
  data: RegionData | null;
  value: CoverageValue;
  onChange: (value: CoverageValue) => void;
  label?: string;
  description?: string;
}

const GLOBAL_OPTION: Option = { level: 'global', code: '', name: 'Global' };

function optionKey(o: Option) {
  return `${o.level}:${o.code}`;
}

/** Resolve a committed value into its display name (reverse lookup). */
function labelForValue(value: CoverageValue, data: RegionData | null): string {
  const { scope_level, scope_code } = value;
  if (!scope_level) return '';
  if (scope_level === 'global') return 'Global';
  if (!data) return scope_code;
  if (scope_level === 'country') {
    return (
      data.countries.find((c) => c.code === scope_code)?.name ?? scope_code
    );
  }
  if (scope_level === 'subregion') {
    return (
      data.subregions.find((s) => s.code === scope_code)?.name ?? scope_code
    );
  }
  if (scope_level === 'region') {
    return data.regions.find((r) => r.code === scope_code)?.name ?? scope_code;
  }
  return scope_code;
}

/**
 * Build the suggestion list for a query. A country match also surfaces the
 * subregion and region it belongs to, so "Nicaragua" offers Nicaragua,
 * Central America, and Americas. Direct subregion/region matches are included
 * too, plus Global. De-duplicated, priority-ordered, and capped.
 */
function buildOptions(query: string, data: RegionData | null): Option[] {
  if (!data) return [];
  const q = query.trim().toLowerCase();
  const out: Option[] = [];
  const seen = new Set<string>();
  const push = (o: Option) => {
    const key = optionKey(o);
    if (!seen.has(key)) {
      seen.add(key);
      out.push(o);
    }
  };

  if (!q || 'global'.includes(q) || 'worldwide'.includes(q)) {
    push(GLOBAL_OPTION);
    if (!q) return out;
  }

  // Rank country matches: exact code, then code prefix, then name.
  const scored = data.countries
    .map((c) => {
      const name = c.name.toLowerCase();
      const code = c.code.toLowerCase();
      let score = -1;
      if (code === q) score = 0;
      else if (code.startsWith(q)) score = 1;
      else if (name.startsWith(q)) score = 2;
      else if (name.includes(q)) score = 3;
      return { c, score };
    })
    .filter((x) => x.score >= 0)
    .sort((a, b) => a.score - b.score || a.c.name.localeCompare(b.c.name))
    .slice(0, 8);

  // Each matched country contributes: the country, then its subregion, then its region.
  for (const { c } of scored) {
    push({ level: 'country', code: c.code, name: c.name });
    if (c.subregion_code && c.subregion_name) {
      push({
        level: 'subregion',
        code: c.subregion_code,
        name: c.subregion_name,
      });
    }
    if (c.region_code && c.region_name) {
      push({ level: 'region', code: c.region_code, name: c.region_name });
    }
  }

  // Direct subregion / region name matches not already surfaced.
  for (const s of data.subregions) {
    if (s.name.toLowerCase().includes(q)) {
      push({ level: 'subregion', code: s.code, name: s.name });
    }
  }
  for (const r of data.regions) {
    if (r.name.toLowerCase().includes(q)) {
      push({ level: 'region', code: r.code, name: r.name });
    }
  }

  return out.slice(0, 40);
}

const LEVEL_LABEL: Record<Option['level'], string> = {
  country: 'Country',
  subregion: 'Subregion',
  region: 'Region',
  global: 'Global',
};

export function CoveragePicker({
  data,
  value,
  onChange,
  label,
  description,
}: Props) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(false);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const committedLabel = labelForValue(value, data);
  const options = useMemo(
    () => (editing ? buildOptions(query, data) : []),
    [editing, query, data]
  );

  useEffect(() => {
    setHighlight(0);
  }, [query]);

  // Revert to the committed value when focus leaves without a selection.
  const revert = () => {
    setEditing(false);
    setOpen(false);
    setQuery('');
  };

  useEffect(() => {
    if (!open) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        revert();
      }
    };
    document.addEventListener('mousedown', onDocMouseDown);
    return () => document.removeEventListener('mousedown', onDocMouseDown);
  }, [open]);

  const commit = (option: Option) => {
    onChange({
      scope_level: option.level,
      scope_code: option.level === 'global' ? '' : option.code,
    });
    setEditing(false);
    setOpen(false);
    setQuery('');
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(h + 1, options.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter') {
      if (open && options[highlight]) {
        e.preventDefault();
        commit(options[highlight]);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      revert();
    }
  };

  const inputValue = editing ? query : committedLabel;
  const hasValue = Boolean(value.scope_level);

  return (
    <div className="flex flex-col gap-2" ref={containerRef}>
      {label && <span className="text-sm font-medium text-text">{label}</span>}
      <div className="relative">
        <span className="input-container flex min-h-10 items-center gap-2 px-3">
          <Globe
            className="h-4 w-4 shrink-0 text-text-muted"
            aria-hidden="true"
          />
          <input
            className="input-field text-sm"
            type="text"
            role="combobox"
            aria-expanded={open}
            aria-autocomplete="list"
            value={inputValue}
            placeholder={t(
              'adminResources.coveragePlaceholder',
              'Search a country, region, or “Global”…'
            )}
            onFocus={() => {
              setEditing(true);
              setQuery('');
              setOpen(true);
            }}
            onChange={(e) => {
              setEditing(true);
              setQuery(e.target.value);
              setOpen(true);
            }}
            onKeyDown={onKeyDown}
            onBlur={revert}
          />
          {hasValue && !editing && (
            <button
              type="button"
              aria-label={t('adminResources.coverageClear', 'Clear coverage')}
              className="shrink-0 text-text-muted transition-colors hover:text-text"
              // mousedown (not click) so it fires before the input blur revert.
              onMouseDown={(e) => {
                e.preventDefault();
                onChange({ scope_level: '', scope_code: '' });
              }}
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
          <ChevronDown
            className={`h-4 w-4 shrink-0 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
        </span>

        {open && options.length > 0 && (
          <ul
            role="listbox"
            className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-y-auto rounded-xl border border-border bg-surface-raised shadow-lg animate-fade-in-scale"
          >
            {options.map((option, index) => {
              const selected =
                value.scope_level === option.level &&
                (option.level === 'global' || value.scope_code === option.code);
              return (
                <li
                  key={optionKey(option)}
                  role="option"
                  aria-selected={selected}
                >
                  <button
                    type="button"
                    // mousedown+preventDefault: select without first blurring the input.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      commit(option);
                    }}
                    onMouseEnter={() => setHighlight(index)}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
                      index === highlight
                        ? 'bg-surface-overlay text-text'
                        : 'text-text-secondary hover:bg-surface-overlay hover:text-text'
                    }`}
                  >
                    <Badge
                      tone={option.level === 'country' ? 'accent' : 'neutral'}
                    >
                      {t(
                        `adminResources.level.${option.level}`,
                        LEVEL_LABEL[option.level]
                      )}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate">
                      {option.name}
                    </span>
                    {option.code && (
                      <span className="shrink-0 font-mono text-xs text-text-muted">
                        {option.code}
                      </span>
                    )}
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

      {description && <p className="text-xs text-text-muted">{description}</p>}
    </div>
  );
}
