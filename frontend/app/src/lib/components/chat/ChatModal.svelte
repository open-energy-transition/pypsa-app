<script lang="ts">
  import { chatModalStore } from '$lib/stores/chatModal.svelte';
  import ChatHeader from './ChatHeader.svelte';
  import ChatRenderer from './ChatRenderer.svelte';
  import ChatInput from './ChatInput.svelte';

  let dragging = $state(false);

  function onPointerDown(e: PointerEvent) {
    e.preventDefault();
    dragging = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent) {
    if (!dragging) return;
    let w = window.innerWidth - e.clientX - 16;
    if (e.shiftKey) {
      const snapTargets = [420, 560, 720, 960];
      let closest = snapTargets[0];
      let minDist = Math.abs(w - snapTargets[0]);
      for (const t of snapTargets) {
        const d = Math.abs(w - t);
        if (d < minDist) { minDist = d; closest = t; }
      }
      w = closest;
    }
    chatModalStore.width = w;
  }

  function onPointerUp(e: PointerEvent) {
    dragging = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }
</script>

{#if chatModalStore.open}
  <div
    role="dialog"
    aria-modal="false"
    aria-label="Chat"
    class="bg-background border-border animate-in slide-in-from-bottom-4 fade-in fixed right-4 bottom-4 z-50 flex h-[640px] max-h-[calc(100vh-2rem)] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border shadow-2xl"
    style="width: {chatModalStore.width}px"
  >
    <div
      class="hover:bg-primary/30 absolute left-0 top-0 h-full w-1.5 cursor-col-resize"
      role="separator"
      aria-label="Resize chat"
      aria-orientation="vertical"
      onpointerdown={onPointerDown}
      onpointermove={onPointerMove}
      onpointerup={onPointerUp}
    ></div>
    <ChatHeader />
    <ChatRenderer />
    <ChatInput />
  </div>
{/if}
