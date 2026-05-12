import { describe, it, expect } from 'vitest';

describe('plotly.js-dist dependency', () => {
  it('imports and has a truthy default export', async () => {
    const m = await import('plotly.js-dist');
    expect(m.default).toBeTruthy();
  });
});
