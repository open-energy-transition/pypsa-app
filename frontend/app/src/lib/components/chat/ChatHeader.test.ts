import { describe, it, expect } from 'vitest';
import { compile } from 'svelte/compiler';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, 'ChatHeader.svelte'), 'utf-8');

describe('ChatHeader', () => {
  it('compiles without errors', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toBeTruthy();
    expect(result.js.code.length).toBeGreaterThan(0);
  });

  it('imports X icon from lucide-svelte', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/import\s*\{[^}]*X[^}]*\}\s*from\s*['"]lucide-svelte['"]/);
  });

  it('imports chatModalStore from the chat modal store', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/chatModal\.svelte/);
    expect(result.js.code).toMatch(/chatModalStore/);
  });

  it('imports chatStore from the chat store', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/chat\.svelte/);
    expect(result.js.code).toMatch(/chatStore/);
  });

  it('displays title "Chat"', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/Chat/);
  });

  it('renders a close button that references chatModalStore', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/chatModalStore/);
  });

  it('shows model badge from chatStore.model', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\.model/);
  });

  it('applies border-b separator for visual separation', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/border-b/);
  });

  it('uses flex layout for the header row', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/flex/);
  });

  it('applies aria-label to the close button for accessibility', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/aria-label/);
    expect(result.js.code).toMatch(/Close/);
  });

  it('applies padding to the header container', () => {
    const result = compile(source, {
      filename: 'ChatHeader.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/p[xy]?-\d/);
  });

  describe('pinned-network chips', () => {
    it('references chatStore.pinnedIds for pinned network ids', () => {
      const result = compile(source, {
        filename: 'ChatHeader.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/\.pinnedIds/);
    });

    it('references chatStore.unpinNetwork for removing chips', () => {
      const result = compile(source, {
        filename: 'ChatHeader.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/unpinNetwork/);
    });

    it('delegates chip remove button click to chatStore.unpinNetwork with the pinnedId', () => {
      const result = compile(source, {
        filename: 'ChatHeader.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/delegated.*unpinNetwork.*pinnedId/);
    });

    it('imports X icon for chip remove buttons', () => {
      const result = compile(source, {
        filename: 'ChatHeader.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/import\s*\{[^}]*X[^}]*\}\s*from\s*['"]lucide-svelte['"]/);
    });

    it('has aria-label on chip remove buttons for accessibility', () => {
      const result = compile(source, {
        filename: 'ChatHeader.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/aria-label/);
      expect(result.js.code).toMatch(/unpin/i);
    });

    it('renders pinned IDs as chips with flex layout for wrapping', () => {
      const result = compile(source, {
        filename: 'ChatHeader.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/flex/);
      expect(result.js.code).toMatch(/flex-wrap/);
    });

    it('applies chip styling with background, border-radius and small text', () => {
      const result = compile(source, {
        filename: 'ChatHeader.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/rounded(?:-full)?/);
      expect(result.js.code).toMatch(/text-xs/);
    });
  });
});
