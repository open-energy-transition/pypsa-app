<script lang="ts">
  import { goto } from '$app/navigation';
  import { chatModalStore } from '$lib/stores/chatModal.svelte';

  let { args = {}, result }: {
    args?: Record<string, unknown>;
    result: { data?: { columns?: string[]; rows?: unknown[][] } } | null;
  } = $props();

  const columns = $derived<string[]>(result?.data?.columns ?? []);
  const rows = $derived<unknown[][]>(result?.data?.rows ?? []);

  function handleRowClick(row: unknown[]) {
    const idIndex = columns.indexOf('id');
    if (idIndex === -1) return;
    const id = row[idIndex];
    chatModalStore.open = false;
    goto(`/database/network?id=${String(id)}`);
  }
</script>

{#if columns.length > 0}
  <div class="max-h-80 max-w-full overflow-auto">
    <table class="w-full text-xs border-collapse">
      <thead>
        <tr class="bg-muted/50">
          {#each columns as col}
            <th class="px-2 py-1.5 text-left font-medium text-muted-foreground border-b border-border">{col}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each rows as row}
          <tr
            class="border-b border-border hover:bg-muted/30 cursor-pointer transition-colors"
            onclick={() => handleRowClick(row)}
            role="link"
            tabindex="0"
            onkeydown={(e) => { if (e.key === 'Enter') handleRowClick(row); }}
          >
            {#each row as cell}
              <td class="px-2 py-1.5">{String(cell ?? '')}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{:else}
  <p class="text-xs text-muted-foreground italic">No network data available.</p>
{/if}
