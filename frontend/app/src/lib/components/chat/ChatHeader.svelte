<script lang="ts">
  import { chatModalStore } from '$lib/stores/chatModal.svelte';
  import { chatStore } from '$lib/stores/chat.svelte';
  import X from '@lucide/svelte/icons/x';
</script>

<div class="shrink-0 border-b border-border px-3 py-2">
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-sm font-semibold">Chat</span>
      {#if chatStore.model}
        <span class="inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
          {chatStore.model}
        </span>
      {/if}
    </div>
    <button
      onclick={() => (chatModalStore.open = false)}
      aria-label="Close chat"
      class="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
    >
      <X class="h-4 w-4" />
    </button>
  </div>

  {#if chatStore.pinnedIds.length > 0}
    <div class="mt-1.5 flex flex-wrap items-center gap-1">
      {#each chatStore.pinnedIds as pinnedId (pinnedId)}
        <span class="inline-flex items-center gap-0.5 rounded-full bg-muted/60 px-2 py-0.5 text-xs text-muted-foreground">
          {pinnedId}
          <button
            onclick={() => chatStore.unpinNetwork(pinnedId)}
            aria-label="Unpin network {pinnedId}"
            class="rounded-full p-0.5 text-muted-foreground hover:bg-muted-foreground/20 hover:text-foreground"
          >
            <X class="h-3 w-3" />
          </button>
        </span>
      {/each}
    </div>
  {/if}
</div>
