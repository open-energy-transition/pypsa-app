import { describe, it, expect } from 'vitest';
import { compile } from 'svelte/compiler';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, 'ChatDataTable.svelte'), 'utf-8');

describe('ChatDataTable', () => {
  it('compiles without errors', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toBeTruthy();
    expect(result.js.code.length).toBeGreaterThan(0);
  });

  it('accepts data prop via $props() rune', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\$props/);
    expect(result.js.code).toMatch(/\bdata\b/);
  });

  it('reads data.columns for table headers', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/columns/);
  });

  it('reads data.rows for table body data', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/rows/);
  });

  it('uses createTable from @tanstack/svelte-table', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/createTable/);
    expect(result.js.code).toMatch(/@tanstack\/svelte-table/);
  });

  it('uses getCoreRowModel for row model', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/getCoreRowModel/);
  });

  it('does not use getSortedRowModel (no sorting in compact mode)', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).not.toMatch(/getSortedRowModel/);
  });

  it('does not use getFilteredRowModel (no filters in compact mode)', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).not.toMatch(/getFilteredRowModel/);
  });

  it('renders column headers from data.columns via TanStack header groups', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/getHeaderGroups/);
  });

  it('renders row cells from data.rows via TanStack row model', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/getRowModel/);
  });

  it('uses compact text-xs font size for table', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/text-xs/);
  });

  it('limits visible rows with max-height and overflow scroll', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/overflow-auto/);
    expect(result.js.code).toMatch(/max-h/);
  });

  it('uses narrow padding for compact cells', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/px-2|px-1\.5|px-1/);
  });

  it('converts data.columns to TanStack column definitions with accessorKey', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/accessorKey/);
  });

  it('converts data.rows to array of objects keyed by column index or name', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\.map/);
  });

  it('uses FlexRender for cell/header rendering', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/FlexRender/);
  });

  it('renders table element markup with proper structure', () => {
    const result = compile(source, {
      filename: 'ChatDataTable.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/getHeaderGroups/);
    expect(result.js.code).toMatch(/getRowModel/);
  });
});
