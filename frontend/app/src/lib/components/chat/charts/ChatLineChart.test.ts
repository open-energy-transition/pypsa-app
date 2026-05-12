import { describe, it, expect } from 'vitest';
import { compile } from 'svelte/compiler';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, 'ChatLineChart.svelte'), 'utf-8');

describe('ChatLineChart', () => {
  it('compiles without errors', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toBeTruthy();
    expect(result.js.code.length).toBeGreaterThan(0);
  });

  it('imports onMount from svelte', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/onMount/);
  });

  it('lazy-imports plotly.js-dist in onMount', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/import\(.*plotly\.js-dist/);
  });

  it('calls Plotly.newPlot with line trace type', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/newPlot/);
    expect(result.js.code).toMatch(/type.*line/);
  });

  it('accepts spec and data props via $props() rune', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\$props/);
    expect(result.js.code).toMatch(/spec/);
    expect(result.js.code).toMatch(/data/);
  });

  it('configures Plotly layout with title, margin, height, and transparent background', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/title/);
    expect(result.js.code).toMatch(/margin/);
    expect(result.js.code).toMatch(/height/);
    expect(result.js.code).toMatch(/paper_bgcolor.*transparent/);
    expect(result.js.code).toMatch(/plot_bgcolor.*transparent/);
  });

  it('passes displayModeBar false and responsive true to Plotly config', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/displayModeBar.*false/);
    expect(result.js.code).toMatch(/responsive.*true/);
  });

  it('binds a div element with class w-full for the chart container', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/w-full/);
    expect(result.js.code).toMatch(/\bdiv\b/);
  });

  it('computes x and y column indices from data.columns.indexOf', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/indexOf/);
  });

  it('maps data.rows to arrays using computed column indices', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\.map/);
    expect(result.js.code).toMatch(/rows/);
  });

  it('uses spec.x and spec.y for column name lookup', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/spec\.x/);
    expect(result.js.code).toMatch(/spec\.y/);
  });

  it('wraps chart rendering in try/catch for error handling', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/try\s*\{/);
    expect(result.js.code).toMatch(/catch/);
    expect(result.js.code).toMatch(/Chart rendering failed/);
  });

  it('renders error message when chart rendering fails', () => {
    const result = compile(source, {
      filename: 'ChatLineChart.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/text-destructive/);
  });
});
