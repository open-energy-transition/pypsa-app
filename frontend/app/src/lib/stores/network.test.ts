import { describe, it, expect, afterEach } from 'vitest';
import { networkStore } from './network.svelte';

describe('networkStore', () => {
  afterEach(() => {
    networkStore.current = null;
  });
  it('starts with null current', () => {
    expect(networkStore.current).toBeNull();
  });

  it('returns the set current value', () => {
    networkStore.current = { id: 'n1', name: 'My Network' };
    expect(networkStore.current).toEqual({ id: 'n1', name: 'My Network' });
  });

  it('returns null after clearing current', () => {
    networkStore.current = { id: 'n1', name: 'My Network' };
    networkStore.current = null;
    expect(networkStore.current).toBeNull();
  });
});
