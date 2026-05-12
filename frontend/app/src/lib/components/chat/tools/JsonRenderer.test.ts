import { describe, it, expect } from 'vitest';
import { compile } from 'svelte/compiler';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, 'JsonRenderer.svelte'), 'utf-8');

describe('JsonRenderer', () => {
  it('compiles without errors', () => {
    const result = compile(source, {
      filename: 'JsonRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toBeTruthy();
    expect(result.js.code.length).toBeGreaterThan(0);
  });

  it('accepts result prop and renders JSON via stringify', () => {
    const result = compile(source, {
      filename: 'JsonRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/JSON\.stringify/);
  });

  it('imports Copy icon from lucide-svelte for the copy button', () => {
    const result = compile(source, {
      filename: 'JsonRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/lucide-svelte/);
    expect(result.js.code).toMatch(/Copy/);
  });

  it('renders a copy button that calls navigator.clipboard.writeText', () => {
    const result = compile(source, {
      filename: 'JsonRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/clipboard/);
    expect(result.js.code).toMatch(/writeText/);
  });

  it('provides visual feedback when copy succeeds (Check icon or copied state)', () => {
    const result = compile(source, {
      filename: 'JsonRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/(copied|Check)/);
  });

  it('uses setTimeout to reset copied state after a delay', () => {
    const result = compile(source, {
      filename: 'JsonRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/setTimeout/);
  });

  it('has an accessible button with aria-label for copy', () => {
    const result = compile(source, {
      filename: 'JsonRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/aria-label/);
    expect(result.js.code).toMatch(/[Cc]opy/);
  });
});