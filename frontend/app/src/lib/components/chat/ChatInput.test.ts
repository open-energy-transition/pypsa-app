import { describe, it, expect } from 'vitest';
import { compile } from 'svelte/compiler';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, 'ChatInput.svelte'), 'utf-8');

describe('ChatInput', () => {
  it('compiles without errors', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toBeTruthy();
    expect(result.js.code.length).toBeGreaterThan(0);
  });

  it('imports Send and Square icons from lucide-svelte', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/import\s*\{[^}]*Send[^}]*\}\s*from\s*['"]lucide-svelte['"]/);
    expect(result.js.code).toMatch(/import\s*\{[^}]*Square[^}]*\}\s*from\s*['"]lucide-svelte['"]/);
  });

  it('imports chatStore from the chat store', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/chat\.svelte/);
    expect(result.js.code).toMatch(/chatStore/);
  });

  it('imports the Button component', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/button\/button\.svelte/);
  });

  it('includes a textarea element', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/textarea/);
  });

  it('binds textarea value to state via bind:value', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    // Svelte 5 bind:value compiles to $.bind_value
    expect(result.js.code).toMatch(/bind_value/);
  });

  it('applies placeholder text to the textarea', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/Ask about your networks/);
  });

  it('applies aria-label="Chat message" to the textarea', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/aria-label/);
    expect(result.js.code).toMatch(/Chat message/);
  });

  it('applies required styling classes to the textarea', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/min-h-\[36px\]/);
    expect(result.js.code).toMatch(/max-h-\[200px\]/);
    expect(result.js.code).toMatch(/flex-1/);
    expect(result.js.code).toMatch(/resize-none/);
    expect(result.js.code).toMatch(/rounded-md/);
    expect(result.js.code).toMatch(/border-border/);
    expect(result.js.code).toMatch(/bg-background/);
    expect(result.js.code).toMatch(/focus:outline-none/);
    expect(result.js.code).toMatch(/focus:ring-1/);
    expect(result.js.code).toMatch(/focus:ring-ring/);
    expect(result.js.code).toMatch(/text-sm/);
  });

  it('prevents sending on Enter without Shift via onkeydown handler', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    // on:keydown compiles to $.delegated('keydown', ...)
    expect(result.js.code).toMatch(/delegated.*keydown/);
  });

  it('does not call send() on Enter when chatStore is running', () => {
    expect(source).toMatch(/function onKey[^}]*chatStore\.running/);
  });

  it('uses $state rune for text binding', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    // $state() compiles to $.state(
    expect(result.js.code).toMatch(/\$\.state\(/);
  });

  it('shows Stop button when chatStore is running', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/chatStore\.running/);
  });

  it('disables Send button when text is empty', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/\.trim\(\)/);
  });

  it('renders an auto-resize effect for the textarea', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    // $effect compiles to $.user_effect
    expect(result.js.code).toMatch(/user_effect/);
  });

  it('auto-resizes by computing line count via split on newlines', () => {
    expect(source).toMatch(/split\(/);
    expect(source).toMatch(/\\n/);
  });

  it('caps textarea rows at a maximum of 8 using Math.min', () => {
    expect(source).toMatch(/\.rows\s*=\s*Math\.min/);
    expect(source).toMatch(/Math\.min\(8,/);
  });

  it('ensures at least 1 row via Math.max', () => {
    expect(source).toMatch(/Math\.max\(1,/);
  });

  it('does not use scrollHeight-based auto-resize', () => {
    expect(source).not.toMatch(/scrollHeight/);
  });

  it('does not use style.height for auto-resize', () => {
    expect(source).not.toMatch(/style\.height/);
  });

  it('applies aria-label to the Stop button for accessibility', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/aria-label/);
    expect(result.js.code).toMatch(/Stop/);
  });

  it('applies aria-label to the Send button for accessibility', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/aria-label/);
    expect(result.js.code).toMatch(/Send/);
  });

  it('wraps the input area in a border-t container with padding', () => {
    const result = compile(source, {
      filename: 'ChatInput.svelte',
      generate: 'client',
    });
    expect(result.js.code).toMatch(/border-t/);
  });

  describe('send() calls chatStore.send with derived context', () => {
    it('imports page from $app/stores for URL-based active network detection', () => {
      expect(source).toMatch(
        /import\s*\{[^}]*page[^}]*\}\s*from\s*['"]\$app\/stores['"]/,
      );
    });

    it('imports networkStore from the network store', () => {
      expect(source).toMatch(/network\.svelte/);
      expect(source).toMatch(/networkStore/);
    });

    it('derives active network context from page URL pathname', () => {
      expect(source).toMatch(/\/database\/network/);
    });

    it('passes pinned_network_ids from chatStore.pinnedIds in the context', () => {
      const result = compile(source, {
        filename: 'ChatInput.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/chatStore.*pinnedIds/);
    });

    it('sets active_network_id and active_network_name from derived active network', () => {
      expect(source).toMatch(/active_network_id/);
      expect(source).toMatch(/active_network_name/);
    });

    it('calls chatStore.send with text and context in the send function', () => {
      const result = compile(source, {
        filename: 'ChatInput.svelte',
        generate: 'client',
      });
      expect(result.js.code).toMatch(/chatStore\.send/);
    });
  });
});
