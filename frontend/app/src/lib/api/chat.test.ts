import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { parseSSEBlock, chat } from './chat';
import { chat as chatFromBarrel } from '$lib/api/client';
import type { AGUIEvent, Message, ChatContext } from '$lib/types/chat';

describe('parseSSEBlock', () => {
  describe('heartbeat / comment lines', () => {
    it('returns null for a block with only comments', () => {
      const block = ':heartbeat\n:keepalive';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });

    it('returns null for a block with only a single comment', () => {
      const block = ': heartbeat';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });

    it('strips comment lines and still parses the event', () => {
      const block = ':heartbeat\nevent: RunStarted\ndata: {"run_id":"r1","model":"m"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('RunStarted');
      expect(result!.data).toEqual({ run_id: 'r1', model: 'm' });
    });

    it('returns null for a block with comments and data but no event', () => {
      const block = ':heartbeat\ndata: {"run_id":"r1","model":"m"}';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });
  });

  describe('multi-line data', () => {
    it('returns null when joined data is not valid JSON (missing comma)', () => {
      const block = 'event: RunStarted\ndata: {"run_id":"r1"\ndata: "model":"m"}';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });

    it('returns null when joined multi-line data is not valid JSON', () => {
      const block = 'event: RunFinished\ndata: {"run_id":"r1"}\ndata: {"stop_reason":"end"}';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });

    it('successfully parses single data line', () => {
      const block = 'event: TextMessageContent\ndata: 42';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('TextMessageContent');
      expect(result!.data).toBe(42);
    });

    it('joins data lines that together form valid JSON', () => {
      // Two data: lines joined with \n, whitespace is valid in JSON
      const block = 'event: RunStarted\ndata: {"run_id":"r1",\ndata: "model":"m"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('RunStarted');
      expect(result!.data).toEqual({ run_id: 'r1', model: 'm' });
    });
  });

  describe('malformed JSON', () => {
    it('returns null when data field is not valid JSON', () => {
      const block = 'event: RunStarted\ndata: {not json}';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });

    it('returns null when data field is a malformed JSON fragment', () => {
      const block = 'event: TextMessageContent\ndata: {"message_id": "msg_1", "delta": "incomplete';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });

    it('returns null when data field is empty string', () => {
      const block = 'event: RunStarted\ndata: ';
      const result = parseSSEBlock(block);
      // JSON.parse('') throws → null
      expect(result).toBeNull();
    });
  });

  describe('valid events', () => {
    it('parses a valid RunStarted event', () => {
      const block = 'event: RunStarted\ndata: {"run_id":"run_abc123","model":"openai/qwen3.5:9b"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('RunStarted');
      expect(result!.data).toEqual({ run_id: 'run_abc123', model: 'openai/qwen3.5:9b' });
    });

    it('parses a valid TextMessageContent event', () => {
      const block = 'event: TextMessageContent\ndata: {"message_id":"msg_1","delta":"Hello"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('TextMessageContent');
      expect(result!.data).toEqual({ message_id: 'msg_1', delta: 'Hello' });
    });

    it('parses a valid RunError event', () => {
      const block = 'event: RunError\ndata: {"run_id":"r1","code":"timeout","message":"timed out"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('RunError');
    });

    it('parses a ToolCallStart event with underscores in tool name', () => {
      const block = 'event: ToolCallStart\ndata: {"tool_call_id":"call_42","tool_name":"get_network_statistics"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('ToolCallStart');
      expect(result!.data).toEqual({ tool_call_id: 'call_42', tool_name: 'get_network_statistics' });
    });

    it('returns null for empty block', () => {
      const block = '';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });

    it('returns null for block with only whitespace', () => {
      const block = '   \n   ';
      const result = parseSSEBlock(block);
      expect(result).toBeNull();
    });

    it('returns AGUIEvent with correct type shape', () => {
      const block = 'event: TextMessageContent\ndata: {"message_id":"m","delta":"d"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      // Verify narrowing works
      const ev: AGUIEvent = result!;
      if (ev.event === 'TextMessageContent') {
        expect(ev.data.message_id).toBe('m');
        expect(ev.data.delta).toBe('d');
      }
    });
  });

  describe('edge cases', () => {
    it('ignores lines without a recognized prefix', () => {
      const block = 'unknown: value\nevent: RunStarted\ndata: {"run_id":"r","model":"m"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('RunStarted');
    });

    it('handles multiple event lines by taking the last one', () => {
      // Per the spec: the loop overwrites eventName, so last event wins
      const block = 'event: RunStarted\nevent: TextMessageContent\ndata: {"message_id":"m","delta":"d"}';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('TextMessageContent');
    });

    it('handles event with trailing whitespace in prefix values', () => {
      const block = 'event:  RunStarted  \ndata:  {"run_id":"r","model":"m"}  ';
      const result = parseSSEBlock(block);
      expect(result).not.toBeNull();
      expect(result!.event).toBe('RunStarted');
      expect(result!.data).toEqual({ run_id: 'r', model: 'm' });
    });
  });
});

// --- Helpers for stream tests ---

function makeSSEBlock(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function makeMockResponse(
  status: number,
  bodyChunks: string[] | null,
): Response {
  const readable = bodyChunks
    ? new ReadableStream({
        start(controller) {
          for (const chunk of bodyChunks) {
            controller.enqueue(new TextEncoder().encode(chunk));
          }
          controller.close();
        },
      })
    : null;

  return {
    ok: status >= 200 && status < 300,
    status,
    body: readable,
    json: async () => ({}),
    text: async () => '',
  } as unknown as Response;
}

function makeAbortSignal(): { signal: AbortSignal; controller: AbortController } {
  const controller = new AbortController();
  return { signal: controller.signal, controller };
}

function dummyStreamRequest(): { messages: Message[]; context: ChatContext } {
  return {
    messages: [{ id: 'u1', role: 'user', content: 'hello', timestamp: '2026-01-01T00:00:00Z' }],
    context: { active_network_id: null, active_network_name: null, pinned_network_ids: [] },
  };
}

describe('chat.stream', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('successful stream', () => {
    it('dispatches parsed SSE events to onEvent handler', async () => {
      const events: AGUIEvent[] = [];
      const chunk = makeSSEBlock('RunStarted', { run_id: 'r1', model: 'm1' }) +
        makeSSEBlock('TextMessageContent', { message_id: 'm1', delta: 'Hi' });

      fetchMock.mockResolvedValue(makeMockResponse(200, [chunk]));

      const { signal } = makeAbortSignal();

      await chat.stream(dummyStreamRequest(), signal, {
        onEvent: (e) => events.push(e),
      });

      expect(events).toHaveLength(2);
      expect(events[0].event).toBe('RunStarted');
      expect(events[1].event).toBe('TextMessageContent');
    });

    it('calls onClose after stream completes', async () => {
      let closed = false;
      fetchMock.mockResolvedValue(makeMockResponse(200, [makeSSEBlock('RunStarted', { run_id: 'r1', model: 'm1' })]));

      const { signal } = makeAbortSignal();

      await chat.stream(dummyStreamRequest(), signal, {
        onEvent: () => {},
        onClose: () => { closed = true; },
      });

      expect(closed).toBe(true);
    });

    it('handles multiple SSE blocks in one chunk', async () => {
      const events: AGUIEvent[] = [];
      const chunk =
        makeSSEBlock('RunStarted', { run_id: 'r1', model: 'm1' }) +
        makeSSEBlock('TextMessageContent', { message_id: 'm1', delta: 'Hello' }) +
        makeSSEBlock('TextMessageContent', { message_id: 'm1', delta: ' world' });

      fetchMock.mockResolvedValue(makeMockResponse(200, [chunk]));

      const { signal } = makeAbortSignal();

      await chat.stream(dummyStreamRequest(), signal, {
        onEvent: (e) => events.push(e),
      });

      expect(events).toHaveLength(3);
    });

    it('handles SSE blocks split across multiple chunks', async () => {
      const events: AGUIEvent[] = [];
      const chunk1 = 'event: RunStarted\ndata: {"run_id":"r1",';
      const chunk2 = '"model":"m1"}\n\n';

      fetchMock.mockResolvedValue(makeMockResponse(200, [chunk1, chunk2]));

      const { signal } = makeAbortSignal();

      await chat.stream(dummyStreamRequest(), signal, {
        onEvent: (e) => events.push(e),
      });

      expect(events).toHaveLength(1);
      expect(events[0].event).toBe('RunStarted');
      expect(events[0].data).toEqual({ run_id: 'r1', model: 'm1' });
    });

    it('handles empty stream (done immediately)', async () => {
      let closed = false;
      fetchMock.mockResolvedValue(makeMockResponse(200, []));

      const { signal } = makeAbortSignal();

      await chat.stream(dummyStreamRequest(), signal, {
        onEvent: () => {},
        onClose: () => { closed = true; },
      });

      expect(closed).toBe(true);
    });
  });

  describe('error handling', () => {
    it('throws when fetch returns non-ok status', async () => {
      fetchMock.mockResolvedValue(makeMockResponse(500, null));

      const { signal } = makeAbortSignal();

      await expect(
        chat.stream(dummyStreamRequest(), signal, { onEvent: () => {} }),
      ).rejects.toThrow('chat stream failed: HTTP 500');
    });

    it('throws when response has no body', async () => {
      fetchMock.mockResolvedValue(makeMockResponse(200, null));

      const { signal } = makeAbortSignal();

      await expect(
        chat.stream(dummyStreamRequest(), signal, { onEvent: () => {} }),
      ).rejects.toThrow('chat stream returned no body');
    });

    it('calls onClose even when fetch fails', async () => {
      let closed = false;
      fetchMock.mockResolvedValue(makeMockResponse(500, null));

      const { signal } = makeAbortSignal();

      await expect(
        chat.stream(dummyStreamRequest(), signal, {
          onEvent: () => {},
          onClose: () => { closed = true; },
        }),
      ).rejects.toThrow();

      expect(closed).toBe(true);
    });

    it('calls onClose even when response has no body', async () => {
      let closed = false;
      fetchMock.mockResolvedValue(makeMockResponse(200, null));

      const { signal } = makeAbortSignal();

      await expect(
        chat.stream(dummyStreamRequest(), signal, {
          onEvent: () => {},
          onClose: () => { closed = true; },
        }),
      ).rejects.toThrow();

      expect(closed).toBe(true);
    });

    it('silently swallows AbortError when fetch rejects due to abort', async () => {
      let closed = false;

      const abortErr = new Error('The operation was aborted');
      abortErr.name = 'AbortError';
      fetchMock.mockRejectedValue(abortErr);

      const { signal } = makeAbortSignal();

      // Must resolve cleanly, not throw
      await expect(
        chat.stream(dummyStreamRequest(), signal, {
          onEvent: () => {},
          onClose: () => { closed = true; },
        }),
      ).resolves.toBeUndefined();

      expect(closed).toBe(true);
    });

    it('silently swallows AbortError during streaming', async () => {
      const events: AGUIEvent[] = [];
      let closed = false;

      const { signal, controller } = makeAbortSignal();

      // Stream that hangs after one event — simulating a real SSE stream mid-flight
      const body = new ReadableStream({
        start(ctrl) {
          ctrl.enqueue(new TextEncoder().encode(
            makeSSEBlock('RunStarted', { run_id: 'r1', model: 'm1' }),
          ));
          signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'AbortError';
            ctrl.error(err);
          });
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      } as unknown as Response);

      const streamPromise = chat.stream(dummyStreamRequest(), signal, {
        onEvent: (e) => events.push(e),
        onClose: () => { closed = true; },
      });

      // Abort after a small delay to let the stream start reading
      setTimeout(() => controller.abort(), 10);

      // Should resolve without throwing
      await expect(streamPromise).resolves.toBeUndefined();

      expect(events.length).toBeGreaterThanOrEqual(1);
      expect(events[0].event).toBe('RunStarted');
      expect(closed).toBe(true);
    });

    it('dispatches read errors to onError handler', async () => {
      let errorCaught: Error | undefined;

      const errorStream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('partial data'));
          controller.error(new Error('stream broke'));
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body: errorStream,
      } as unknown as Response);

      const { signal } = makeAbortSignal();

      await chat.stream(dummyStreamRequest(), signal, {
        onEvent: () => {},
        onError: (err) => { errorCaught = err; },
      });

      expect(errorCaught).toBeDefined();
      expect(errorCaught!.message).toBe('stream broke');
    });
  });

  describe('request contract', () => {
    it('sends POST with JSON body and credentials', async () => {
      fetchMock.mockResolvedValue(makeMockResponse(200, []));

      const { signal } = makeAbortSignal();
      const req = dummyStreamRequest();

      await chat.stream(req, signal, { onEvent: () => {} });

      expect(fetchMock).toHaveBeenCalledWith('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
        signal,
        credentials: 'include',
      });
    });
  });
});

describe('chat.health', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns health data on success', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, model: 'openai/gpt-4o' }),
    } as unknown as Response);

    const result = await chat.health();

    expect(result).toEqual({ ok: true, model: 'openai/gpt-4o' });
  });

  it('throws on non-ok response', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({}),
    } as unknown as Response);

    await expect(chat.health()).rejects.toThrow('chat health: HTTP 503');
  });

  it('sends request with credentials', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, model: 'm' }),
    } as unknown as Response);

    await chat.health();

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/chat/health', {
      credentials: 'include',
    });
  });

  it('throws enriched error when fetch rejects (network failure)', async () => {
    const networkErr = new Error('Failed to fetch');
    fetchMock.mockRejectedValue(networkErr);

    await expect(chat.health()).rejects.toThrow('chat health check failed: Failed to fetch');
  });
});

describe('client.ts barrel export for chat namespace', () => {
  it('re-exports the chat namespace from client.ts', () => {
    expect(chatFromBarrel).toBeDefined();
    expect(chatFromBarrel).toBe(chat);
  });

  it('exposes stream method via the barrel', () => {
    expect(typeof chatFromBarrel.stream).toBe('function');
  });

  it('exposes health method via the barrel', () => {
    expect(typeof chatFromBarrel.health).toBe('function');
  });
});
