<script lang="ts">
  import { chatStore } from '$lib/stores/chat.svelte';
  import { Send, Square } from 'lucide-svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let text = $state('');
  let textareaEl = $state<HTMLTextAreaElement>();

  function send() {
    if (!text.trim()) return;
    chatStore.send(text);
    text = '';
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!chatStore.running) send();
    }
  }

  $effect(() => {
    const lines = text.split('\n').length;
    if (textareaEl) textareaEl.rows = Math.min(8, Math.max(1, lines));
  });
</script>

<div class="shrink-0 border-t border-border p-2">
  <div class="flex items-end gap-2">
    <textarea
      bind:value={text}
      bind:this={textareaEl}
      onkeydown={onKey}
      placeholder="Ask about your networks…"
      aria-label="Chat message"
      class="min-h-[36px] max-h-[200px] flex-1 resize-none rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
      rows="1"
    ></textarea>
    {#if chatStore.running}
      <Button size="icon" variant="destructive" onclick={() => chatStore.stop()} aria-label="Stop" title="Stop">
        <Square class="h-4 w-4" />
      </Button>
    {:else}
      <Button size="icon" onclick={send} disabled={!text.trim()} aria-label="Send" title="Send">
        <Send class="h-4 w-4" />
      </Button>
    {/if}
  </div>
</div>
