import { describe, it, expect } from 'vitest';
import { compile } from 'svelte/compiler';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, 'NetworkCardRenderer.svelte'), 'utf-8');

function compileClient() {
  return compile(source, { filename: 'NetworkCardRenderer.svelte', generate: 'client' });
}

describe('NetworkCardRenderer', () => {
  it('compiles without errors', () => {
    const result = compileClient();
    expect(result.js.code).toBeTruthy();
    expect(result.js.code.length).toBeGreaterThan(0);
  });

  it('accepts args and result props via $props() rune', () => {
    const code = compileClient().js.code;
    expect(code).toMatch(/\$props/);
    expect(code).toMatch(/args/);
    expect(code).toMatch(/result/);
  });

  it('reads the network detail from result.data.network', () => {
    expect(source).toMatch(/result\?\.data\?\.network/);
  });

  it('renders the network name with font-semibold styling', () => {
    expect(source).toMatch(/network\.name/);
    expect(source).toMatch(/font-semibold/);
  });

  it('renders the id with an "id:" label', () => {
    expect(source).toMatch(/network\.id/);
    expect(source).toMatch(/id:/);
  });

  it('renders ownership derived from is_owner', () => {
    expect(source).toMatch(/network\.is_owner/);
    expect(source).toMatch(/owner:/);
  });

  it('renders last_updated_at under a "modified:" label when present', () => {
    expect(source).toMatch(/network\.last_updated_at/);
    expect(source).toMatch(/modified:/);
  });

  it('renders visibility when present', () => {
    expect(source).toMatch(/network\.visibility/);
    expect(source).toMatch(/visibility:/);
  });

  it('summarises components_count under a "components:" label', () => {
    expect(source).toMatch(/components_count/);
    expect(source).toMatch(/components:/);
  });

  it('uses card container with Tailwind border, rounded, and padding classes', () => {
    expect(source).toMatch(/rounded-md/);
    expect(source).toMatch(/border/);
    expect(source).toMatch(/p-3/);
  });

  it('uses text-xs text-muted-foreground class for secondary fields', () => {
    expect(source).toMatch(/text-xs/);
    expect(source).toMatch(/text-muted-foreground/);
  });

  it('imports goto from $app/navigation for open-in-app link', () => {
    expect(source).toMatch(/\$app\/navigation/);
    expect(source).toMatch(/goto/);
  });

  it('imports chatModalStore for closing modal on open-in-app click', () => {
    expect(source).toMatch(/chatModalStore/);
  });

  it('navigates to /database/network?id=<id> when open-in-app link is clicked', () => {
    expect(source).toMatch(/\/database\/network\?id=/);
  });

  it('closes chat panel before navigating on open-in-app click', () => {
    expect(source).toMatch(/chatModalStore\.open\s*=\s*false/);
  });

  it('renders an open-in-app button element', () => {
    expect(source).toMatch(/<button[\s\S]*Open in app/);
  });
});
