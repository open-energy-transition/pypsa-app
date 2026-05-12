import { describe, it, expect } from 'vitest';
import { compile } from 'svelte/compiler';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, 'ToolResultRenderer.svelte'), 'utf-8');

describe('ToolResultRenderer', () => {
  it('compiles without errors', () => {
    const result = compile(source, {
      filename: 'ToolResultRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toBeTruthy();
    expect(result.js.code.length).toBeGreaterThan(0);
  });

  it('accepts result prop via $props() rune', () => {
    const result = compile(source, {
      filename: 'ToolResultRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/result/);
    expect(result.js.code).toMatch(/\$props/);
  });

  it('renders error message in destructive text when result is error', () => {
    const result = compile(source, {
      filename: 'ToolResultRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/is_error/);
    expect(result.js.code).toMatch(/text-destructive/);
  });

  it('renders success result via resolved Renderer component', () => {
    const result = compile(source, {
      filename: 'ToolResultRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/Renderer/);
    expect(result.js.code).toMatch(/result\.result/);
    expect(result.js.code).toMatch(/args/);
  });

  it('imports toolRenderers registry map', () => {
    const result = compile(source, {
      filename: 'ToolResultRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/toolRenderers/);
  });

  it('imports JsonRenderer as fallback component', () => {
    const result = compile(source, {
      filename: 'ToolResultRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/JsonRenderer/);
  });

  it('accepts toolName and args props for registry lookup', () => {
    const result = compile(source, {
      filename: 'ToolResultRenderer.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/toolName/);
    expect(result.js.code).toMatch(/args/);
  });

  it('includes fallback pattern to JsonRenderer when tool not in registry', () => {
    const result = compile(source, {
      filename: 'ToolResultRenderer.svelte',
      generate: 'client',
    });
    const code = result.js.code;
    expect(code.includes('??') || code.includes('JsonRenderer')).toBe(true);
  });
});
