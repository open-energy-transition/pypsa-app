<script lang="ts">
  import { page } from '$app/stores';
  import { chatStore } from '$lib/stores/chat.svelte';
  import { networkStore } from '$lib/stores/network.svelte';
  import type {
    Message,
    AssistantSegment,
    ReasoningSegment,
    ToolCallSegment,
    ToolCall,
    ToolResult,
    ChatContext,
  } from '$lib/types/chat';
  import {
    Reasoning,
    ReasoningTrigger,
    ReasoningContent,
  } from '$lib/components/ai-elements/reasoning';
  import {
    Tool,
    ToolHeader,
    ToolContent,
    ToolInput,
    ToolOutput,
  } from '$lib/components/ai-elements/tool';
  import { Response } from '$lib/components/ai-elements/response';
  import {
    Message as MessageRoot,
    MessageContent,
    MessageActions,
    MessageAction,
  } from '$lib/components/ai-elements/message';
  import { Suggestion } from '$lib/components/ai-elements/suggestion';
  import ToolResultRenderer from './ToolResultRenderer.svelte';
  import { toolRenderers } from './toolRenderers';
  import { Textarea } from '$lib/components/ui/textarea';
  import { Button } from '$lib/components/ui/button';
  import CopyIcon from '@lucide/svelte/icons/copy';
  import CheckIcon from '@lucide/svelte/icons/check';
  import RefreshIcon from '@lucide/svelte/icons/refresh-cw';
  import PencilIcon from '@lucide/svelte/icons/pencil';
  import SparklesIcon from '@lucide/svelte/icons/sparkles';

  type ReasoningChild = ReasoningSegment | ToolCallSegment;
  type RenderItem =
    | { kind: 'reasoning_group'; children: ReasoningChild[] }
    | { kind: 'inline'; segment: AssistantSegment };

  function buildPlan(segments: AssistantSegment[]): RenderItem[] {
    const plan: RenderItem[] = [];
    let group: { kind: 'reasoning_group'; children: ReasoningChild[] } | null = null;
    for (const s of segments) {
      const isReasoningPhase =
        s.kind === 'reasoning' || (s.kind === 'tool_call' && s.phase === 'reasoning');
      if (isReasoningPhase) {
        if (!group) {
          group = { kind: 'reasoning_group', children: [] };
          plan.push(group);
        }
        group.children.push(s as ReasoningChild);
      } else {
        group = null;
        plan.push({ kind: 'inline', segment: s });
      }
    }
    return plan;
  }

  function statusToToolState(s: ToolCall['status']) {
    switch (s) {
      case 'streaming': return 'input-streaming' as const;
      case 'running': return 'input-available' as const;
      case 'complete': return 'output-available' as const;
      case 'error': return 'output-error' as const;
    }
  }

  const activeNetwork = $derived.by(() => {
    if (!$page.url.pathname.startsWith('/database/network')) return null;
    return networkStore.current;
  });

  const context: ChatContext = $derived({
    active_network_id: activeNetwork?.id ?? null,
    active_network_name: activeNetwork?.name ?? null,
    pinned_network_ids: chatStore.pinnedIds,
  });

  const suggestions = $derived.by(() => {
    if (activeNetwork) {
      return [
        `Summarize ${activeNetwork.name} in two sentences.`,
        'List the top 5 generators by capacity.',
        'What carriers are present?',
      ];
    }
    return [
      'List my networks.',
      'Compare two networks.',
      'What can you do?',
    ];
  });

  function onSuggestion(s: string) {
    chatStore.send(s, context);
  }

  let copiedIds = $state<Set<string>>(new Set());

  function flashCopied(id: string) {
    copiedIds = new Set([...copiedIds, id]);
    setTimeout(() => {
      copiedIds = new Set([...copiedIds].filter((x) => x !== id));
    }, 2000);
  }

  async function copyToClipboard(text: string): Promise<boolean> {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        // fall through to legacy path
      }
    }
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.setAttribute('readonly', '');
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }

  async function copyAssistant(msg: Message) {
    if (msg.role !== 'assistant') return;
    const text = msg.segments
      .filter((s): s is Extract<AssistantSegment, { kind: 'text' }> => s.kind === 'text')
      .map((s) => s.text)
      .join('\n');
    if (await copyToClipboard(text)) flashCopied(msg.id);
  }

  async function copyUser(msg: Message) {
    if (msg.role !== 'user') return;
    if (await copyToClipboard(msg.content)) flashCopied(msg.id);
  }

  function regenerate() {
    chatStore.regenerate(context);
  }

  let editingId = $state<string | null>(null);
  let editText = $state('');

  function startEdit(msg: Message) {
    if (msg.role !== 'user') return;
    editingId = msg.id;
    editText = msg.content;
  }

  function cancelEdit() {
    editingId = null;
    editText = '';
  }

  function saveEdit(messageId: string) {
    const text = editText;
    editingId = null;
    editText = '';
    chatStore.editAndResend(messageId, text, context);
  }

  function onEditKey(e: KeyboardEvent, messageId: string) {
    if (e.key === 'Escape') { e.preventDefault(); cancelEdit(); return; }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveEdit(messageId); }
  }

  function resultFromSeg(seg: { result?: ToolResult }): ToolResult | undefined {
    return seg.result;
  }

  function hasCustomRenderer(name: string): boolean {
    return name in toolRenderers;
  }

  const TOOL_LABELS: Record<string, string> = {
    list_networks: 'List networks',
    get_network_detail: 'Network detail',
    get_network_statistics: 'Network statistics',
  };

  function humanizeToolName(name: string): string {
    if (TOOL_LABELS[name]) return TOOL_LABELS[name];
    const cleaned = name.replace(/^tool[-_]/i, '').replace(/[_-]+/g, ' ').trim();
    if (!cleaned) return name;
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  }

  let scrollerEl = $state<HTMLDivElement>();
  let logEl = $state<HTMLDivElement>();
  let stickToBottom = true;
  const STICK_PX = 80;

  function handleScroll() {
    if (!logEl) return;
    const distance = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight;
    stickToBottom = distance < STICK_PX;
  }

  $effect(() => {
    chatStore.messages;
    if (!logEl || !stickToBottom) return;
    requestAnimationFrame(() => {
      scrollerEl?.scrollIntoView({ behavior: 'instant' });
    });
  });
</script>

<div
  bind:this={logEl}
  onscroll={handleScroll}
  class="min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-4"
  role="log"
  aria-live="polite"
  aria-busy={chatStore.status === 'streaming' || chatStore.status === 'connecting'}
>
  {#if chatStore.messages.length === 0}
    <div class="text-muted-foreground mt-8 flex flex-col items-center gap-4 text-center">
      <SparklesIcon class="size-8 opacity-60" />
      <div>
        <p class="text-sm font-medium">Ask anything about your networks</p>
        <p class="mt-1 text-xs">Try one of these to get started.</p>
      </div>
      <div class="flex flex-wrap items-center justify-center gap-2">
        {#each suggestions as s}
          <Suggestion suggestion={s} onclick={onSuggestion} />
        {/each}
      </div>
    </div>
  {/if}

  <div class="flex min-w-0 max-w-full flex-col gap-4">
    {#each chatStore.messages as msg, i (msg.id)}
      {@const isLast = i === chatStore.messages.length - 1}
      {@const isLastAssistant = isLast && msg.role === 'assistant'}
      {#if msg.role === 'user'}
        {#if editingId === msg.id}
          <div class="ml-auto flex w-full max-w-full flex-col gap-2">
            <Textarea
              bind:value={editText}
              onkeydown={(e) => onEditKey(e, msg.id)}
              placeholder="Edit and resend…"
              rows={3}
              class="w-full resize-none"
            />
            <div class="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onclick={cancelEdit}>Cancel</Button>
              <Button size="sm" onclick={() => saveEdit(msg.id)} disabled={!editText.trim() || chatStore.running}>
                Save &amp; resend
              </Button>
            </div>
          </div>
        {:else}
          <div class="group flex w-full items-center justify-end gap-1" data-msg-id={msg.id}>
            <div class="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
              <MessageAction
                tooltip={copiedIds.has(msg.id) ? 'Copied!' : 'Copy'}
                label="Copy message"
                onclick={() => copyUser(msg)}
              >
                {#if copiedIds.has(msg.id)}
                  <CheckIcon class="size-3.5 text-emerald-500" />
                {:else}
                  <CopyIcon class="size-3.5" />
                {/if}
              </MessageAction>
              <MessageAction
                tooltip="Edit"
                label="Edit message"
                disabled={chatStore.running}
                onclick={() => startEdit(msg)}
              >
                <PencilIcon class="size-3.5" />
              </MessageAction>
            </div>
            <div class="bg-secondary text-foreground max-w-[80%] rounded-lg px-4 py-2 text-sm">
              {msg.content}
            </div>
          </div>
        {/if}
      {:else}
        <MessageRoot from="assistant" data-msg-id={msg.id}>
          <MessageContent class="w-full min-w-0 max-w-full overflow-hidden">
            {@const plan = buildPlan(msg.segments)}
            {#each plan as item, j (j)}
              {#if item.kind === 'reasoning_group'}
                <Reasoning
                  isStreaming={isLastAssistant && chatStore.running && j === plan.length - 1}
                  defaultOpen
                >
                  <ReasoningTrigger />
                  <ReasoningContent>
                    {#each item.children as child (child.kind === 'tool_call' ? child.id : `r:${child.message_id}:${j}`)}
                      {#if child.kind === 'reasoning' && child.text}
                        <Response content={child.text} />
                      {:else if child.kind === 'tool_call'}
                        <Tool>
                          <ToolHeader
                            type={humanizeToolName(child.name)}
                            state={statusToToolState(child.status)}
                          />
                          <ToolContent>
                            {#if child.args}
                              <ToolInput input={child.args} />
                            {/if}
                            {#if child.result}
                              {#if child.result.is_error}
                                <ToolOutput errorText={child.result.error ?? 'Tool error'} />
                              {:else if hasCustomRenderer(child.name)}
                                <div class="space-y-2 p-4">
                                  <h4 class="text-muted-foreground text-xs font-medium tracking-wide uppercase">Result</h4>
                                  <ToolResultRenderer
                                    toolName={child.name}
                                    args={child.args}
                                    result={child.result}
                                  />
                                </div>
                              {:else}
                                <ToolOutput output={child.result.result} />
                              {/if}
                            {/if}
                          </ToolContent>
                        </Tool>
                      {/if}
                    {/each}
                  </ReasoningContent>
                </Reasoning>
              {:else if item.segment.kind === 'text' && item.segment.text}
                <Response content={item.segment.text} />
              {:else if item.segment.kind === 'tool_call'}
                {@const seg = item.segment}
                <Tool>
                  <ToolHeader type={humanizeToolName(seg.name)} state={statusToToolState(seg.status)} />
                  <ToolContent>
                    {#if seg.args}
                      <ToolInput input={seg.args} />
                    {/if}
                    {#if seg.result}
                      {#if seg.result.is_error}
                        <ToolOutput errorText={seg.result.error ?? 'Tool error'} />
                      {:else if hasCustomRenderer(seg.name)}
                        <div class="space-y-2 p-4">
                          <h4 class="text-muted-foreground text-xs font-medium tracking-wide uppercase">Result</h4>
                          <ToolResultRenderer
                            toolName={seg.name}
                            args={seg.args}
                            result={resultFromSeg(seg)!}
                          />
                        </div>
                      {:else}
                        <ToolOutput output={seg.result.result} />
                      {/if}
                    {/if}
                  </ToolContent>
                </Tool>
              {/if}
            {/each}
          </MessageContent>
          {#if !chatStore.running || !isLast}
            <MessageActions class="opacity-0 transition-opacity group-hover:opacity-100">
              <MessageAction
                tooltip={copiedIds.has(msg.id) ? 'Copied!' : 'Copy'}
                label="Copy"
                onclick={() => copyAssistant(msg)}
              >
                {#if copiedIds.has(msg.id)}
                  <CheckIcon class="size-3.5 text-emerald-500" />
                {:else}
                  <CopyIcon class="size-3.5" />
                {/if}
              </MessageAction>
              {#if isLastAssistant}
                <MessageAction tooltip="Regenerate" label="Regenerate" onclick={regenerate}>
                  <RefreshIcon class="size-3.5" />
                </MessageAction>
              {/if}
            </MessageActions>
          {/if}
        </MessageRoot>
      {/if}
    {/each}
    <div bind:this={scrollerEl}></div>
  </div>
</div>
