import { beforeEach, describe, expect, it } from 'vitest';
import { migrateLegacyStorageKey } from './legacyStorage';

describe('migrateLegacyStorageKey', () => {
  beforeEach(() => localStorage.clear());

  it('moves a legacy value to the new key', () => {
    localStorage.setItem('market-helm-token', 'abc');
    migrateLegacyStorageKey('markethelm-token', 'market-helm-token');
    expect(localStorage.getItem('markethelm-token')).toBe('abc');
    expect(localStorage.getItem('market-helm-token')).toBeNull();
  });

  it('never overwrites an existing new value', () => {
    localStorage.setItem('market-helm-token', 'old');
    localStorage.setItem('markethelm-token', 'new');
    migrateLegacyStorageKey('markethelm-token', 'market-helm-token');
    expect(localStorage.getItem('markethelm-token')).toBe('new');
    expect(localStorage.getItem('market-helm-token')).toBeNull();
  });

  it('does nothing when there is no legacy value', () => {
    migrateLegacyStorageKey('markethelm-token', 'market-helm-token');
    expect(localStorage.getItem('markethelm-token')).toBeNull();
  });
});
