<script lang="ts">
  import { chatModalStore } from '$lib/stores/chatModal.svelte';
  import MessageSquareIcon from '@lucide/svelte/icons/message-square';
</script>

{#if !chatModalStore.open}
  <button
    type="button"
    onclick={() => (chatModalStore.open = true)}
    aria-label="Open chat"
    title="Open chat"
    class="bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:ring-ring fixed right-4 bottom-4 z-40 flex size-12 items-center justify-center rounded-full shadow-lg transition-colors focus-visible:outline-none focus-visible:ring-2"
  >
    <MessageSquareIcon class="size-5" />
  </button>
{/if}
