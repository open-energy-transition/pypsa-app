import { describe, it, expect, beforeEach, vi } from 'vitest';
import { features, initFeatures } from './features.svelte';
import { version } from '$lib/api/client';

vi.mock('$lib/api/client', () => ({
  version: { get: vi.fn() },
}));

describe('features store', () => {
  beforeEach(() => {
    features.runsEnabled = false;
    features.chatEnabled = false;
    vi.mocked(version.get).mockReset();
  });

  describe('defaults', () => {
    it('runsEnabled defaults to false', () => {
      expect(features.runsEnabled).toBe(false);
    });

    it('chatEnabled defaults to false', () => {
      expect(features.chatEnabled).toBe(false);
    });
  });

  describe('initFeatures()', () => {
    it('reads runsEnabled from snakedispatch_backends and chatEnabled from chat_enabled', async () => {
      vi.mocked(version.get).mockResolvedValue({
        version: '1.0.0',
        snakedispatch_backends: ['cluster-a'],
        chat_enabled: true,
      });

      await initFeatures();

      expect(features.runsEnabled).toBe(true);
      expect(features.chatEnabled).toBe(true);
    });

    it('sets runsEnabled=false when snakedispatch_backends is empty', async () => {
      vi.mocked(version.get).mockResolvedValue({
        version: '1.0.0',
        snakedispatch_backends: [],
        chat_enabled: false,
      });

      await initFeatures();

      expect(features.runsEnabled).toBe(false);
      expect(features.chatEnabled).toBe(false);
    });

    it('sets runsEnabled=false when snakedispatch_backends is missing', async () => {
      vi.mocked(version.get).mockResolvedValue({
        version: '1.0.0',
      });

      await initFeatures();

      expect(features.runsEnabled).toBe(false);
      expect(features.chatEnabled).toBe(false);
    });

    it('treats missing chat_enabled as false', async () => {
      vi.mocked(version.get).mockResolvedValue({
        version: '1.0.0',
        snakedispatch_backends: ['cluster-a'],
      });

      await initFeatures();

      expect(features.runsEnabled).toBe(true);
      expect(features.chatEnabled).toBe(false);
    });

    it('leaves both flags as false when version.get() throws', async () => {
      vi.mocked(version.get).mockRejectedValue(new Error('Network error'));

      features.runsEnabled = true;
      features.chatEnabled = true;

      await initFeatures();

      expect(features.runsEnabled).toBe(false);
      expect(features.chatEnabled).toBe(false);
    });
  });
});
