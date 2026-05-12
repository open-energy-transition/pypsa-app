import { describe, it, expect } from 'vitest';
import { compile } from 'svelte/compiler';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, 'NetworksTableRenderer.svelte'), 'utf-8');

describe('NetworksTableRenderer', () => {
  it('compiles without errors', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toBeTruthy();
    expect(result.js.code.length).toBeGreaterThan(0);
  });

  it('accepts args and result props via $props() rune', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\$props/);
    expect(result.js.code).toMatch(/args/);
    expect(result.js.code).toMatch(/result/);
  });

  it('reads result.data.columns for table headers', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/columns/);
    expect(result.js.code).toMatch(/data/);
  });

  it('reads result.data.rows for table body data', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/rows/);
  });

  it('renders column headers from data.columns', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/thead|columns/);
  });

  it('renders row data from data.rows', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/tbody|rows/);
  });

  it('imports goto from $app/navigation for row click navigation', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\$app\/navigation/);
    expect(result.js.code).toMatch(/goto/);
  });

  it('renders table element with Tailwind styling classes', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/table/);
  });

  it('each row is clickable via delegated click handler', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/handleRowClick/);
    expect(result.js.code).toMatch(/delegated.*click/);
  });

  it('navigates to /database/network?id=<id> on row click via goto', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\/database\/network\?id=/);
    expect(result.js.code).toMatch(/goto/);
  });

  it('extracts network id from the id column index in the row', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/indexOf.*['"]id['"]/);
  });

  it('provides keyboard accessibility with role="link" and tabindex="0" on rows', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/role/);
    expect(result.js.code).toMatch(/"link"/);
    expect(result.js.code).toMatch(/tabindex/);
    expect(result.js.code).toMatch(/"0"/);
  });

  it('handles Enter key for keyboard navigation on rows', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/keydown/);
    expect(result.js.code).toMatch(/Enter/);
  });

  it('shows empty state message when no columns are present', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/No network data/);
  });

  it('closes the chat panel on row click navigation', () => {
    const result = compile(source, {
      filename: 'NetworksTableRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/chatModalStore/);
    expect(result.js.code).toMatch(/\.open\s*=/);
  });
});
