<script lang="ts">
  import Copy from '@lucide/svelte/icons/copy';
  import Check from '@lucide/svelte/icons/check';

  let { args = {}, result }: {
    args?: Record<string, unknown>;
    result: unknown;
  } = $props();

  let copied = $state(false);

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
      copied = true;
      setTimeout(() => {
        copied = false;
      }, 2000);
    } catch {
      // clipboard API unavailable — silently fail
    }
  }
</script>

<div class="relative group">
  <button
    type="button"
    class="absolute top-2 right-2 rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
    onclick={copyToClipboard}
    aria-label="Copy to clipboard"
    title="Copy to clipboard"
  >
    {#if copied}
      <Check class="h-3.5 w-3.5 text-green-600" />
    {:else}
      <Copy class="h-3.5 w-3.5" />
    {/if}
  </button>
  <pre class="text-xs whitespace-pre-wrap overflow-auto max-h-60">{JSON.stringify(result, null, 2)}</pre>
</div>
