import type {
  Message,
  AssistantMessage,
  AssistantSegment,
  TextSegment,
  ReasoningSegment,
  ToolCallSegment,
  ChatContext,
  AGUIEvent,
} from '$lib/types/chat';
import { chat } from '$lib/api/client';
import { safeRandomUUID } from '$lib/uuid';

type RunStatus = 'idle' | 'connecting' | 'streaming' | 'error' | 'done';

class ChatStore {
  #messages = $state<Message[]>([]);
  #pinned = $state<string[]>([]);
  #status = $state<RunStatus>('idle');
  #error = $state<string | null>(null);
  #model = $state<string | null>(null);
  #abort: AbortController | null = null;
  #currentAssistant: AssistantMessage | null = null;
  #currentPhase: 'reasoning' | 'content' = 'content';

  get messages() { return this.#messages; }
  get pinnedIds() { return this.#pinned; }
  get status() { return this.#status; }
  get running() { return this.#status === 'connecting' || this.#status === 'streaming'; }
  get error() { return this.#error; }
  get model() { return this.#model; }

  stop() {
    this.#abort?.abort();
  }

  reset() {
    this.stop();
    this.#messages = [];
    this.#pinned = [];
    this.#status = 'idle';
    this.#error = null;
    this.#model = null;
  }

  pinNetwork(id: string) {
    if (!this.#pinned.includes(id)) this.#pinned = [...this.#pinned, id];
  }
  unpinNetwork(id: string) {
    this.#pinned = this.#pinned.filter((p) => p !== id);
  }

  regenerate(context: ChatContext): Promise<void> | void {
    if (this.running) return;
    let lastUserIdx = -1;
    for (let i = this.#messages.length - 1; i >= 0; i--) {
      if (this.#messages[i].role === 'user') { lastUserIdx = i; break; }
    }
    if (lastUserIdx < 0) return;
    const lastUser = this.#messages[lastUserIdx] as Extract<Message, { role: 'user' }>;
    this.#messages = this.#messages.slice(0, lastUserIdx);
    return this.send(lastUser.content, context);
  }

  editAndResend(messageId: string, newContent: string, context: ChatContext): Promise<void> | void {
    if (this.running) return;
    if (!newContent.trim()) return;
    const idx = this.#messages.findIndex((m) => m.id === messageId);
    if (idx < 0) return;
    if (this.#messages[idx].role !== 'user') return;
    this.#messages = this.#messages.slice(0, idx);
    return this.send(newContent.trim(), context);
  }

  async send(content: string, context: ChatContext): Promise<void> {
    if (!content.trim() || !['idle', 'done', 'error'].includes(this.#status)) return;

    const userMsg: Message = {
      id: safeRandomUUID(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toISOString(),
    };
    this.#messages = [...this.#messages, userMsg];

    this.#abort = new AbortController();
    this.#status = 'connecting';
    this.#currentAssistant = null;
    this.#error = null;

    try {
      await chat.stream(
        { messages: this.#messages, context: { ...context, pinned_network_ids: this.#pinned } },
        this.#abort.signal,
        {
          onEvent: (e) => this.#handleEvent(e),
          onError: (err) => {
            this.#status = 'error';
            this.#error = err.message;
          },
        },
      );
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        // user-initiated stop is not an error
      } else {
        this.#status = 'error';
        this.#error = err instanceof Error ? err.message : 'Unknown error';
      }
    } finally {
      if (this.#status !== 'error') this.#status = 'done';
      this.#abort = null;
      this.#currentAssistant = null;
    }
  }

  #handleEvent(e: AGUIEvent) {
    switch (e.event) {
      case 'RunStarted': {
        this.#status = 'streaming';
        this.#model = e.data.model;
        this.#currentPhase = 'content';
        const draft: AssistantMessage = {
          id: safeRandomUUID(),
          role: 'assistant',
          segments: [],
          timestamp: new Date().toISOString(),
        };
        this.#messages = [...this.#messages, draft];
        this.#currentAssistant = this.#messages[this.#messages.length - 1] as AssistantMessage;
        break;
      }
      case 'TextMessageContent':
        this.#currentPhase = 'content';
        this.#updateAssistant((m) => {
          const last = m.segments[m.segments.length - 1];
          if (last && last.kind === 'text' && last.message_id === e.data.message_id) {
            last.text += e.data.delta;
          } else {
            const seg: TextSegment = {
              kind: 'text',
              message_id: e.data.message_id,
              text: e.data.delta,
            };
            m.segments.push(seg);
          }
        });
        break;
      case 'ReasoningMessageContent':
        this.#currentPhase = 'reasoning';
        this.#updateAssistant((m) => {
          const last = m.segments[m.segments.length - 1];
          if (last && last.kind === 'reasoning' && last.message_id === e.data.message_id) {
            last.text += e.data.delta;
          } else {
            const seg: ReasoningSegment = {
              kind: 'reasoning',
              message_id: e.data.message_id,
              text: e.data.delta,
            };
            m.segments.push(seg);
          }
        });
        break;
      case 'ToolCallStart':
        this.#updateAssistant((m) => {
          const seg: ToolCallSegment = {
            kind: 'tool_call',
            id: e.data.tool_call_id,
            name: e.data.tool_name,
            args_partial: '',
            status: 'streaming',
            phase: this.#currentPhase,
          };
          m.segments.push(seg);
        });
        break;
      case 'ToolCallArgs':
        this.#updateAssistant((m) => {
          const seg = findToolCall(m.segments, e.data.tool_call_id);
          if (seg) seg.args_partial += e.data.delta;
        });
        break;
      case 'ToolCallEnd':
        this.#updateAssistant((m) => {
          const seg = findToolCall(m.segments, e.data.tool_call_id);
          if (seg) {
            seg.args = e.data.args;
            seg.status = 'running';
          }
        });
        break;
      case 'ToolCallResult':
        this.#updateAssistant((m) => {
          const seg = findToolCall(m.segments, e.data.tool_call_id);
          if (seg) {
            seg.result = e.data;
            seg.status = e.data.is_error ? 'error' : 'complete';
          }
        });
        break;
      case 'RunError':
        this.#status = 'error';
        this.#error = e.data.message;
        this.#appendErrorMessage(`${e.data.code}: ${e.data.message}`);
        break;
    }
  }

  #updateAssistant(mutate: (m: AssistantMessage) => void) {
    if (!this.#currentAssistant) return;
    mutate(this.#currentAssistant);
    // Replace the array reference to trigger reactivity.
    this.#messages = [...this.#messages];
  }

  #appendErrorMessage(text: string) {
    this.#messages = [...this.#messages, {
      id: safeRandomUUID(),
      role: 'assistant' as const,
      segments: [{ kind: 'text', message_id: 'error', text: `⚠️ ${text}` }],
      timestamp: new Date().toISOString(),
    }];
  }
}

function findToolCall(segments: AssistantSegment[], id: string): ToolCallSegment | undefined {
  for (let i = segments.length - 1; i >= 0; i--) {
    const s = segments[i];
    if (s.kind === 'tool_call' && s.id === id) return s;
  }
  return undefined;
}

export const chatStore = new ChatStore();
