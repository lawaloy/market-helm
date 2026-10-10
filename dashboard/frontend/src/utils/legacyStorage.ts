/**
 * One-time move of a localStorage value saved under a pre-rename key (market-helm-*) to its
 * markethelm-* key, so a browser that already has a session or theme keeps it after the rename.
 * Storage may be blocked or full; failures are ignored (the app then behaves as a fresh browser).
 */
export function migrateLegacyStorageKey(key: string, legacyKey: string): void {
  try {
    const legacyValue = localStorage.getItem(legacyKey);
    if (legacyValue === null) return;
    if (localStorage.getItem(key) === null) localStorage.setItem(key, legacyValue);
    localStorage.removeItem(legacyKey);
  } catch {
    // Blocked or unavailable storage must not break boot.
  }
}
