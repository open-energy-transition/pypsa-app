<script lang="ts">
  import type { ToolResult } from '$lib/types/chat';
  import { toolRenderers } from './toolRenderers';
  import JsonRenderer from './tools/JsonRenderer.svelte';

  let { toolName = '', args = {}, result }: {
    toolName?: string;
    args?: Record<string, unknown>;
    result: ToolResult;
  } = $props();

  const Renderer = $derived(toolRenderers[toolName] ?? JsonRenderer);
</script>

{#if result.is_error}
  <div class="text-xs text-destructive">{result.error}</div>
{:else}
  <Renderer {args} result={result.result} />
{/if}
