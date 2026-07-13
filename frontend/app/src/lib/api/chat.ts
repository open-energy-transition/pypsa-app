import type { Message, ChatContext, AGUIEvent, ToolResult } from '$lib/types/chat';

const API_BASE = '/api/v1';

export interface StreamRequest {
  messages: Message[];
  context: ChatContext;
}

interface BackendToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

interface BackendAssistantMessage {
  id: string;
  role: 'assistant';
  content: string;
  reasoning?: string;
  tool_calls?: BackendToolCall[];
  tool_results?: ToolResult[];
  timestamp: string;
}

type BackendMessage = BackendAssistantMessage | { id: string; role: 'user'; content: string; timestamp: string };

export function toBackendMessage(m: Message): BackendMessage {
  if (m.role === 'user') {
    return { id: m.id, role: 'user', content: m.content, timestamp: m.timestamp };
  }
  const text: string[] = [];
  const reasoning: string[] = [];
  const tool_calls: BackendToolCall[] = [];
  const tool_results: ToolResult[] = [];
  for (const s of m.segments) {
    if (s.kind === 'text') text.push(s.text);
    else if (s.kind === 'reasoning') reasoning.push(s.text);
    else {
      tool_calls.push({ id: s.id, name: s.name, args: s.args ?? {} });
      if (s.result) tool_results.push(s.result);
    }
  }
  return {
    id: m.id,
    role: 'assistant',
    content: text.join(''),
    reasoning: reasoning.length > 0 ? reasoning.join('') : undefined,
    tool_calls: tool_calls.length > 0 ? tool_calls : undefined,
    tool_results: tool_results.length > 0 ? tool_results : undefined,
    timestamp: m.timestamp,
  };
}

export interface StreamHandlers {
  onEvent: (event: AGUIEvent) => void;
  onError?: (err: Error) => void;
  onClose?: () => void;
}

export const chat = {
  async stream(req: StreamRequest, signal: AbortSignal, handlers: StreamHandlers): Promise<void> {
    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...req, messages: req.messages.map(toBackendMessage) }),
        signal,
        credentials: 'include',
      });

      if (!res.ok) {
        throw new Error(`chat stream failed: HTTP ${res.status}`);
      }
      if (!res.body) {
        throw new Error('chat stream returned no body');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let idx;
          while ((idx = buffer.indexOf('\n\n')) >= 0) {
            const block = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const event = parseSSEBlock(block);
            if (event) handlers.onEvent(event);
          }
        }
      } catch (err) {
        if ((err as Error).name === 'AbortError') {
          // expected — user pressed Stop
        } else {
          handlers.onError?.(err as Error);
        }
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        // expected — user pressed Stop before/during fetch
      } else {
        throw err;
      }
    } finally {
      handlers.onClose?.();
    }
  },

  async health(): Promise<{ ok: boolean; model: string }> {
    try {
      const r = await fetch(`${API_BASE}/chat/health`, { credentials: 'include' });
      if (!r.ok) throw new Error(`chat health: HTTP ${r.status}`);
      return r.json();
    } catch (err) {
      if (err instanceof Error && err.message.startsWith('chat health:')) {
        throw err;
      }
      throw new Error(`chat health check failed: ${(err as Error).message}`);
    }
  },
};

export function parseSSEBlock(block: string): AGUIEvent | null {
  let eventName = '';
  let data = '';
  for (const line of block.split('\n')) {
    if (line.startsWith(':')) continue; // comment / heartbeat
    if (line.startsWith('event:')) eventName = line.slice(6).trim();
    else if (line.startsWith('data:')) data += (data ? '\n' : '') + line.slice(5).trim();
  }
  if (!eventName) return null;
  try {
    return { event: eventName as AGUIEvent['event'], data: JSON.parse(data) } as AGUIEvent;
  } catch {
    return null;
  }
}
