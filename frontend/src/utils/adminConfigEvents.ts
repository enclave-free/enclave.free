export const ADMIN_CONFIG_CHANGED_EVENT = 'enclave:admin-config-changed';

export interface AdminConfigChangedDetail {
  areas: string[];
}

/** Read the non-mutating refresh hint returned by Sage after direct writes. */
export function readAdminConfigAffectedAreas(payload: unknown): string[] {
  if (!payload || typeof payload !== 'object') return [];
  const areas = (payload as Record<string, unknown>)[
    'admin_config_affected_areas'
  ];
  if (!Array.isArray(areas)) return [];
  return [
    ...new Set(
      areas.filter((area): area is string => typeof area === 'string')
    ),
  ];
}

/** Tell mounted Admin settings views to refetch after Sage completed a write. */
export function notifyAdminConfigChanged(areas: string[]): void {
  const uniqueAreas = [...new Set(areas)];
  if (typeof window !== 'undefined' && uniqueAreas.length > 0) {
    window.dispatchEvent(
      new CustomEvent<AdminConfigChangedDetail>(ADMIN_CONFIG_CHANGED_EVENT, {
        detail: { areas: uniqueAreas },
      })
    );
  }
}

/** Subscribe a mounted settings view to the direct-write areas it owns. */
export function subscribeAdminConfigChanges(
  areas: readonly string[],
  refresh: () => void
): () => void {
  if (typeof window === 'undefined') return () => {};
  const watched = new Set(areas);
  const listener = (event: Event) => {
    const detail = (event as CustomEvent<AdminConfigChangedDetail>).detail;
    if (detail?.areas?.some((area) => watched.has(area))) refresh();
  };
  window.addEventListener(ADMIN_CONFIG_CHANGED_EVENT, listener);
  return () => window.removeEventListener(ADMIN_CONFIG_CHANGED_EVENT, listener);
}
