<script lang="ts">
  import { goto } from '$app/navigation';
  import { chatModalStore } from '$lib/stores/chatModal.svelte';

  interface NetworkDetail {
    id?: string;
    name?: string;
    filename?: string;
    visibility?: string;
    is_owner?: boolean;
    last_updated_at?: string | null;
    components_count?: Record<string, number>;
  }

  let { args = {}, result }: {
    args?: Record<string, unknown>;
    result: { summary?: string; data?: { network?: NetworkDetail } } | null;
  } = $props();

  const network = $derived<NetworkDetail | undefined>(result?.data?.network);

  const componentsSummary = $derived<string>(
    Object.entries(network?.components_count ?? {})
      .slice(0, 6)
      .map(([k, v]) => `${k}=${v}`)
      .join(', '),
  );

  function handleOpenInApp() {
    chatModalStore.open = false;
    goto(`/database/network?id=${String(network?.id ?? '')}`);
  }
</script>

{#if network}
  <div class="rounded-md border border-border p-3 space-y-1">
    <div class="font-semibold text-sm">{network.name ?? network.filename ?? 'unnamed'}</div>
    <div class="text-xs text-muted-foreground">id: {network.id ?? ''}</div>
    <div class="text-xs text-muted-foreground">
      owner: {network.is_owner ? 'you' : 'another user'}
    </div>
    {#if network.visibility}
      <div class="text-xs text-muted-foreground">visibility: {network.visibility}</div>
    {/if}
    {#if network.last_updated_at}
      <div class="text-xs text-muted-foreground">modified: {network.last_updated_at}</div>
    {/if}
    {#if componentsSummary}
      <div class="text-xs text-muted-foreground">components: {componentsSummary}</div>
    {/if}
    <button
      type="button"
      class="mt-2 inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      onclick={handleOpenInApp}
    >
      Open in app
    </button>
  </div>
{/if}
