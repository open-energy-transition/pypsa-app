import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type {
  UserMessage,
  Message,
  AssistantMessage,
  ToolCallSegment,
  ToolResult,
} from '$lib/types/chat';

import { chatStore } from './chat.svelte';

function textOf(m: AssistantMessage): string {
  return m.segments
    .filter((s): s is Extract<AssistantMessage['segments'][number], { kind: 'text' }> => s.kind === 'text')
    .map((s) => s.text)
    .join('');
}

function reasoningOf(m: AssistantMessage): string {
  return m.segments
    .filter((s): s is Extract<AssistantMessage['segments'][number], { kind: 'reasoning' }> => s.kind === 'reasoning')
    .map((s) => s.text)
    .join('');
}

function toolCallsOf(m: AssistantMessage): ToolCallSegment[] {
  return m.segments.filter((s): s is ToolCallSegment => s.kind === 'tool_call');
}

function toolResultsOf(m: AssistantMessage): ToolResult[] {
  return toolCallsOf(m)
    .map((tc) => tc.result)
    .filter((r): r is ToolResult => r !== undefined);
}

function makeEmptyBody(): ReadableStream {
  return new ReadableStream({
    start(controller) {
      controller.close();
    },
  });
}

function makeSSEBlock(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

describe('chatStore', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        body: makeEmptyBody(),
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('messages', () => {
    it('defaults to an empty array', () => {
      const store = new (Object.getPrototypeOf(chatStore).constructor)();
      expect(store.messages).toEqual([]);
      expect(store.messages).toHaveLength(0);
    });

    it('returns an array from the singleton', () => {
      expect(Array.isArray(chatStore.messages)).toBe(true);
    });
  });

  describe('send()', () => {
    it('appends a user message to the messages array', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('List my networks', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(1);
      const msg = store.messages[0] as UserMessage;
      expect(msg.role).toBe('user');
      expect(msg.content).toBe('List my networks');
    });

    it('creates a user message with correct shape', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: 'net_42',
        active_network_name: 'My Network',
        pinned_network_ids: ['net_1', 'net_2'],
      });

      const msg = store.messages[0] as UserMessage;
      expect(msg.role).toBe('user');
      expect(msg.id).toBeTruthy();
      expect(typeof msg.id).toBe('string');
      expect(msg.content).toBe('Hello');
      expect(msg.timestamp).toBeTruthy();
      expect(() => new Date(msg.timestamp)).not.toThrow();
      expect(new Date(msg.timestamp).toISOString()).toBe(msg.timestamp);
    });

    it('trims whitespace from content', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('  List my networks  ', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const msg = store.messages[0] as UserMessage;
      expect(msg.content).toBe('List my networks');
    });

    it('does not append a message when content is empty string', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(0);
    });

    it('does not append a message when content is whitespace-only', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('   ', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(0);
    });

    it('appends multiple messages in order', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('First', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      await store.send('Second', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      await store.send('Third', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(3);
      const contents = store.messages.map((m: Message) => (m as UserMessage).content);
      expect(contents).toEqual(['First', 'Second', 'Third']);
    });

    it('assigns unique ids to each message', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Msg A', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      await store.send('Msg B', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const ids = store.messages.map((m: Message) => m.id);
      expect(ids[0]).not.toBe(ids[1]);
    });

    it('gives each message a unique timestamp when called rapidly', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Fast A', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      await store.send('Fast B', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const t1 = new Date(store.messages[0].timestamp).getTime();
      const t2 = new Date(store.messages[1].timestamp).getTime();
      expect(t2).toBeGreaterThanOrEqual(t1);
    });
  });

  describe('RunStarted handler', () => {
    it('appends an assistant message shell when RunStarted event is received', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_1', model: 'test-model' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(2);
      expect(store.messages[0].role).toBe('user');
      expect(store.messages[1].role).toBe('assistant');
    });

    it('creates assistant message shell with correct default shape', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_2', model: 'gpt-4' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Query', {
        active_network_id: 'net_a',
        active_network_name: 'Net A',
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(assistant.role).toBe('assistant');
      expect(assistant.id).toBeTruthy();
      expect(typeof assistant.id).toBe('string');
      expect(textOf(assistant)).toBe('');
      expect(assistant.timestamp).toBeTruthy();
      expect(() => new Date(assistant.timestamp)).not.toThrow();
      expect(toolCallsOf(assistant)).toEqual([]);
      expect(toolResultsOf(assistant)).toEqual([]);
    });

    it('does not create a shell when no RunStarted event arrives', async () => {
      // Empty stream — no events at all
      const body = new ReadableStream({
        start(controller) {
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Only me', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Only the user message should be present
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe('user');
    });

    it('stops being running after RunStarted stream completes', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_3', model: 'm' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      const promise = store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('connecting');

      await promise;

      expect(store.status).toBe('done');
    });

    it('produces unique assistant message ids for different runs', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      // First run
      const body1 = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_a', model: 'm1' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        body: body1,
      });

      await store.send('First', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Second run
      const body2 = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_b', model: 'm2' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        body: body2,
      });

      await store.send('Second', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(4); // user, assistant, user, assistant
      const firstAssistant = store.messages[1];
      const secondAssistant = store.messages[3];
      expect(firstAssistant.id).not.toBe(secondAssistant.id);
    });
  });

  describe('send() guard when already running', () => {
    it('ignores a second send call while a stream is active', async () => {
      let closeStream: (() => void) | undefined;

      fetchMock.mockImplementation((_url: string, _options: RequestInit) => {
        const body = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(
                makeSSEBlock('RunStarted', { run_id: 'run_slow', model: 'm' }),
              ),
            );
            // Don't close — stream stays open until test signals completion
            closeStream = () => controller.close();
          },
        });

        return Promise.resolve({ ok: true, status: 200, body });
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      const promise = store.send('First', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // While still running, a second send should be ignored
      await store.send('Second', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Close the stream so the first send completes
      closeStream!();
      await promise;

      // Only the first user message (and its assistant shell) should exist
      expect(store.messages).toHaveLength(2);
      expect(store.messages[0].role).toBe('user');
      expect((store.messages[0] as UserMessage).content).toBe('First');
    });
  });

  describe('TextMessageContent handler', () => {
    it('appends delta to current assistant message content', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_1', model: 'test-model' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'msg_1', delta: 'Hello' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'msg_1', delta: ' world' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Query', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(2);
      const assistant = store.messages[1] as AssistantMessage;
      expect(assistant.role).toBe('assistant');
      expect(textOf(assistant)).toBe('Hello world');
    });

    it('is a no-op when no current assistant exists (no prior RunStarted)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('TextMessageContent', { message_id: 'msg_1', delta: 'orphan' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hey', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Only the user message should exist — no assistant shell
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe('user');
    });

    it('handles single TextMessageContent delta', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_3', model: 'm' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'msg', delta: 'Hi!' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Yo', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(textOf(assistant)).toBe('Hi!');
    });
  });

  describe('ReasoningMessageContent handler', () => {
    it('appends delta to current assistant message reasoning', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_1', model: 'test-model' }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'msg_1', delta: 'Let me think about this' }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'msg_1', delta: ' carefully...' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Query', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(2);
      const assistant = store.messages[1] as AssistantMessage;
      expect(assistant.role).toBe('assistant');
      expect(reasoningOf(assistant)).toBe('Let me think about this carefully...');
    });

    it('is a no-op when no current assistant exists (no prior RunStarted)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('ReasoningMessageContent', { message_id: 'msg_1', delta: 'orphan reasoning' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hey', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Only the user message should exist — no assistant shell
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe('user');
    });

    it('handles single ReasoningMessageContent delta', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_3', model: 'm' }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'msg', delta: 'Analyzing request...' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({
        ok: true,
        status: 200,
        body,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Reason', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(reasoningOf(assistant)).toBe('Analyzing request...');
    });
  });

  describe('ToolCallStart handler', () => {
    it('pushes a tool_call entry into the current assistant message', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tc', model: 'm' }),
            ),
          );
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_1', tool_name: 'list_networks' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Query', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(2);
      const assistant = store.messages[1] as AssistantMessage;
      expect(toolCallsOf(assistant)).toHaveLength(1);
      expect(toolCallsOf(assistant)[0].id).toBe('tc_1');
      expect(toolCallsOf(assistant)[0].name).toBe('list_networks');
      expect(toolCallsOf(assistant)[0].status).toBe('streaming');
    });

    it('sets args_partial to empty string on new tool call', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tc2', model: 'm' }),
            ),
          );
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_2', tool_name: 'get_network_detail' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Detail', {
        active_network_id: 'net_x',
        active_network_name: 'Net X',
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(toolCallsOf(assistant)[0].args_partial).toBe('');
    });

    it('does nothing when no assistant message exists (no RunStarted)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_orphan', tool_name: 'list_networks' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Orphan tool call', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Only the user message should be present — ToolCallStart without RunStarted is a no-op
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe('user');
    });
  });

  describe('ToolCallArgs handler', () => {
    it('appends delta to the matching tool call args_partial', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tca', model: 'm' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_1', tool_name: 'list_networks' }) +
                makeSSEBlock('ToolCallArgs', { tool_call_id: 'tc_1', delta: '{"limit":' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Query', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(toolCallsOf(assistant)).toHaveLength(1);
      expect(toolCallsOf(assistant)[0].args_partial).toBe('{"limit":');
    });

    it('accumulates deltas from multiple ToolCallArgs events', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tca2', model: 'm' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_2', tool_name: 'get_network' }) +
                makeSSEBlock('ToolCallArgs', { tool_call_id: 'tc_2', delta: '{"id":' }) +
                makeSSEBlock('ToolCallArgs', { tool_call_id: 'tc_2', delta: '"net_42"}' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Detail', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(toolCallsOf(assistant)[0].args_partial).toBe('{"id":"net_42"}');
    });

    it('does nothing when no assistant message exists (no RunStarted)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('ToolCallArgs', { tool_call_id: 'tc_orphan', delta: '{}' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Orphan args', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Only the user message should be present — ToolCallArgs without RunStarted is a no-op
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe('user');
    });

    it('is a no-op when tool_call_id does not match any existing tool call', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_nomatch', model: 'm' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_known', tool_name: 'list' }) +
                makeSSEBlock('ToolCallArgs', { tool_call_id: 'tc_unknown', delta: '{}' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Mismatch', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      // The known tool call should be unchanged (args_partial still empty)
      expect(toolCallsOf(assistant)).toHaveLength(1);
      expect(toolCallsOf(assistant)[0].args_partial).toBe('');
    });
  });

  describe('ToolCallEnd handler', () => {
    it('sets parsed args and status=running on the matching tool call', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tce', model: 'm' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_1', tool_name: 'list_networks' }) +
                makeSSEBlock('ToolCallArgs', { tool_call_id: 'tc_1', delta: '{"limit":' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 'tc_1', args: { limit: 10, sort_by: 'name' } }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Query', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(toolCallsOf(assistant)).toHaveLength(1);
      expect(toolCallsOf(assistant)[0].id).toBe('tc_1');
      expect(toolCallsOf(assistant)[0].args).toEqual({ limit: 10, sort_by: 'name' });
      expect(toolCallsOf(assistant)[0].status).toBe('running');
      // args_partial should preserve what was accumulated before ToolCallEnd
      expect(toolCallsOf(assistant)[0].args_partial).toBe('{"limit":');
    });

    it('does nothing when tool_call_id does not match any existing tool call', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tce2', model: 'm' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_known', tool_name: 'list' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 'tc_unknown', args: {} }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Mismatch', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(toolCallsOf(assistant)).toHaveLength(1);
      expect(toolCallsOf(assistant)[0].status).toBe('streaming');
      expect(toolCallsOf(assistant)[0].args).toBeUndefined();
    });

    it('does nothing when no assistant message exists (no RunStarted)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('ToolCallEnd', { tool_call_id: 'tc_orphan', args: {} }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Orphan', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Only the user message should be present — ToolCallEnd without RunStarted is a no-op
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe('user');
    });
  });

  describe('ToolCallResult handler', () => {
    it('appends result to tool_results and sets status to complete when is_error is false', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tcr', model: 'm' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_1', tool_name: 'list_networks' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 'tc_1', args: { limit: 10 } }) +
                makeSSEBlock('ToolCallResult', {
                  tool_call_id: 'tc_1',
                  result: { summary: 'Found 3 networks', data: [] },
                  is_error: false,
                  error: null,
                }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('List', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(toolResultsOf(assistant)).toHaveLength(1);
      expect(toolResultsOf(assistant)[0].tool_call_id).toBe('tc_1');
      expect(toolResultsOf(assistant)[0].result).toEqual({ summary: 'Found 3 networks', data: [] });
      expect(toolResultsOf(assistant)[0].is_error).toBe(false);
      expect(toolResultsOf(assistant)[0].error).toBeNull();

      // Status on the matching tool call should be 'complete'
      expect(toolCallsOf(assistant)).toHaveLength(1);
      expect(toolCallsOf(assistant)[0].status).toBe('complete');
    });

    it('appends result to tool_results and sets status to error when is_error is true', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tcr_err', model: 'm' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_err', tool_name: 'get_network_detail' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 'tc_err', args: { id: 'net_missing' } }) +
                makeSSEBlock('ToolCallResult', {
                  tool_call_id: 'tc_err',
                  result: null,
                  is_error: true,
                  error: 'Network not found',
                }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Get network', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      expect(toolResultsOf(assistant)).toHaveLength(1);
      expect(toolResultsOf(assistant)[0].tool_call_id).toBe('tc_err');
      expect(toolResultsOf(assistant)[0].result).toBeNull();
      expect(toolResultsOf(assistant)[0].is_error).toBe(true);
      expect(toolResultsOf(assistant)[0].error).toBe('Network not found');

      // Status on the matching tool call should be 'error'
      expect(toolCallsOf(assistant)).toHaveLength(1);
      expect(toolCallsOf(assistant)[0].status).toBe('error');
    });

    it('does nothing when no assistant message exists (no RunStarted)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('ToolCallResult', {
                tool_call_id: 'tc_orphan',
                result: { data: [] },
                is_error: false,
                error: null,
              }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Orphan result', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // Only the user message should be present — ToolCallResult without RunStarted is a no-op
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe('user');
    });

    it('does nothing when tool_call_id does not match any existing tool call', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_tcr_nomatch', model: 'm' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc_known', tool_name: 'list_networks' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 'tc_known', args: {} }) +
                makeSSEBlock('ToolCallResult', {
                  tool_call_id: 'tc_unknown',
                  result: { data: [] },
                  is_error: false,
                  error: null,
                }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Mismatch', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      const assistant = store.messages[1] as AssistantMessage;
      // Orphan results (no matching tool_call segment) are dropped — there is
      // no card they could attach to. The known tool call stays at 'running'.
      expect(toolResultsOf(assistant)).toHaveLength(0);
      expect(toolCallsOf(assistant)).toHaveLength(1);
      expect(toolCallsOf(assistant)[0].status).toBe('running');
    });
  });

  describe('stop()', () => {
    it('triggers the AbortController abort and resets running state when stop is called mid-stream', async () => {
      let abortFired = false;

      fetchMock.mockImplementation((_url: string, options: RequestInit) => {
        const signal = options.signal as AbortSignal;

        const body = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(
                makeSSEBlock('RunStarted', { run_id: 'run_abort', model: 'm' }),
              ),
            );
            controller.enqueue(
              new TextEncoder().encode(
                makeSSEBlock('TextMessageContent', { message_id: 'msg', delta: 'partial' }),
              ),
            );

            signal.addEventListener('abort', () => {
              abortFired = true;
              controller.error(new DOMException('The operation was aborted', 'AbortError'));
            });
          },
        });

        return Promise.resolve({ ok: true, status: 200, body });
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      const promise = store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('connecting');

      store.stop();

      // Verify AbortController.abort() was called — the signal listener fired
      expect(abortFired).toBe(true);

      await promise;

      expect(store.status).toBe('done');
      // The user message plus the partial assistant shell should remain
      expect(store.messages.length).toBeGreaterThanOrEqual(1);
      expect(store.messages[0].role).toBe('user');
    });

    it('does not throw when stop is called while no stream is active', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      expect(() => store.stop()).not.toThrow();
      expect(store.status).toBe('idle');
    });
  });

  describe('status state machine', () => {
    it('defaults to idle', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      expect(store.status).toBe('idle');
    });

    it('transitions idle → connecting → streaming → done on a successful send', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_sm', model: 'm' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      expect(store.status).toBe('idle');

      const promise = store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('connecting');

      await promise;

      expect(store.status).toBe('done');
    });

    it('transitions to streaming when RunStarted event arrives', async () => {
      let resolveStream: () => void;
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_sm2', model: 'm' }),
            ),
          );
          // Don't close yet — let the test observe the intermediate state
          resolveStream = () => controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      const promise = store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // After the stream processes the RunStarted block, status should be 'streaming'
      await vi.waitFor(() => {
        expect(store.status).toBe('streaming');
      });

      resolveStream!();
      await promise;
      expect(store.status).toBe('done');
    });

    it('blocks send when status is not idle', async () => {
      let resolveStream: () => void;
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_block', model: 'm' }),
            ),
          );
          resolveStream = () => controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      const first = store.send('First', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      // status should be 'connecting' and second send should be blocked
      expect(store.status).toBe('connecting');
      await store.send('Second', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      resolveStream!();
      await first;

      expect(store.messages).toHaveLength(2);
      expect((store.messages[0] as UserMessage).content).toBe('First');
    });

    it('exposes status via the singleton', () => {
      expect(typeof chatStore.status).toBe('string');
      expect(chatStore.status).toBe('idle');
    });

    it('allows send after RunError puts status into error state', async () => {
      const errorBody = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunError', { run_id: 'run_err', code: 'server_error', message: 'Something went wrong' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body: errorBody });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Fail', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');

      // Second send from error state should not be blocked
      const okBody = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_ok', model: 'm' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body: okBody });

      await store.send('Retry', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('done');
      expect(store.messages).toHaveLength(4); // first user msg + ⚠️ assistant + second user msg + assistant shell
      expect((store.messages[2] as UserMessage).content).toBe('Retry');
    });

    it('allows send after network error puts status into error state', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network failure'));

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Fail', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');

      // Retry should work from error state
      const okBody = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_retry', model: 'm' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body: okBody });

      await store.send('Retry', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('done');
      expect(store.messages).toHaveLength(3);
    });
  });

  describe('error handling', () => {
    it('defaults error to null', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      expect(store.error).toBeNull();
    });

    it('captures error message when fetch rejects with a non-abort error', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network failure'));

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');
      expect(store.error).toBe('Network failure');
    });

    it('captures error message when HTTP response is not ok', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        body: null,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');
      expect(store.error).toBe('chat stream failed: HTTP 500');
    });

    it('captures error message when stream body is null', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        body: null,
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');
      expect(store.error).toBe('chat stream returned no body');
    });

    it('captures error from reader stream via onError callback', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_1', model: 'm' }),
            ),
          );
          controller.error(new Error('Reader stream broke'));
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');
      expect(store.error).toBe('Reader stream broke');
    });

    it('does not treat AbortError as an error — status becomes done', async () => {
      let abortFired = false;

      fetchMock.mockImplementation((_url: string, options: RequestInit) => {
        const signal = options.signal as AbortSignal;

        const body = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(
                makeSSEBlock('RunStarted', { run_id: 'run_abort', model: 'm' }),
              ),
            );

            signal.addEventListener('abort', () => {
              abortFired = true;
              controller.error(new DOMException('The operation was aborted', 'AbortError'));
            });
          },
        });

        return Promise.resolve({ ok: true, status: 200, body });
      });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      const promise = store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      store.stop();
      expect(abortFired).toBe(true);

      await promise;

      expect(store.status).toBe('done');
      expect(store.error).toBeNull();
    });

    it('clears error when a new send starts', async () => {
      fetchMock.mockRejectedValueOnce(new Error('First failure'));

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');
      expect(store.error).toBe('First failure');

      // Start a new send — error should be cleared immediately
      const okBody = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_retry', model: 'm' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body: okBody });

      await store.send('Retry', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('done');
      expect(store.error).toBeNull();
    });

    it('captures error message from RunError SSE event', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunError', { run_id: 'run_sse_err', code: 'server_error', message: 'Model overload' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');
      expect(store.error).toBe('Model overload');
    });

    it('appends a ⚠️ assistant message on RunError SSE event', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunError', { run_id: 'run_warn', code: 'timeout', message: 'timed out' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages).toHaveLength(2); // user + ⚠️ assistant
      const assistantMsg = store.messages[1];
      expect(assistantMsg.role).toBe('assistant');
      expect(textOf(assistantMsg)).toBe('⚠️ timeout: timed out');
    });

    it('exposes error via the singleton as null initially', () => {
      expect(chatStore.error).toBeNull();
    });
  });

  describe('model getter', () => {
    it('defaults to null', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      expect(store.model).toBeNull();
    });

    it('is set to the model string from RunStarted event', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_model_1', model: 'gpt-4' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValue({ ok: true, status: 200, body });

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.model).toBe('gpt-4');
    });

    it('updates to the latest model on subsequent runs', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      const body1 = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_m1', model: 'gpt-4' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body: body1 });

      await store.send('First', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.model).toBe('gpt-4');

      const body2 = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_m2', model: 'claude-3' }),
            ),
          );
          controller.close();
        },
      });

      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body: body2 });

      await store.send('Second', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.model).toBe('claude-3');
    });
  });

  describe('running getter', () => {
    it('returns false when status is idle', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      expect(store.running).toBe(false);
    });

    it('returns true when status is connecting', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      // Force status to connecting by starting a send on a slow stream
      let resolveStream: () => void;
      const body = new ReadableStream({
        start(controller) {
          resolveStream = () => controller.close();
        },
      });
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body });
      const promise = store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      expect(store.running).toBe(true);
      resolveStream!();
      return promise;
    });

    it('returns true when status is streaming', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      let resolveStream: () => void;
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_r', model: 'm' }),
            ),
          );
          resolveStream = () => controller.close();
        },
      });
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body });
      const promise = store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      await vi.waitFor(() => {
        expect(store.running).toBe(true);
      });
      resolveStream!();
      return promise;
    });

    it('returns false when status is done', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_d', model: 'm' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body });
      await store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      expect(store.running).toBe(false);
    });

    it('returns false when status is error', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      fetchMock.mockRejectedValueOnce(new Error('fail'));
      await store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      expect(store.running).toBe(false);
    });

    it('returns false after stop() aborts a running stream', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      let resolveStream: () => void;
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'run_s', model: 'm' }),
            ),
          );
          const originalClose = controller.close.bind(controller);
          resolveStream = originalClose;
        },
      });
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, body });
      const promise = store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });
      await vi.waitFor(() => {
        expect(store.running).toBe(true);
      });
      store.stop();
      resolveStream!();
      await promise;
      expect(store.running).toBe(false);
    });

    it('exposes running via the singleton', () => {
      expect(typeof chatStore.running).toBe('boolean');
    });
  });

  describe('pinnedIds / pinNetwork / unpinNetwork', () => {
    it('defaults pinnedIds to an empty array', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;
      expect(store.pinnedIds).toEqual([]);
    });

    it('adds an id when pinNetwork is called', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      store.pinNetwork('a');

      expect(store.pinnedIds).toEqual(['a']);
    });

    it('does not duplicate an id when pinNetwork is called twice with the same id', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      store.pinNetwork('a');
      store.pinNetwork('a');

      expect(store.pinnedIds).toEqual(['a']);
    });

    it('accumulates distinct ids in insertion order when pinNetwork is called for a then b', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      store.pinNetwork('a');
      store.pinNetwork('b');

      expect(store.pinnedIds).toEqual(['a', 'b']);
    });

    it('removes an id when unpinNetwork is called', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      store.pinNetwork('a');
      store.pinNetwork('b');
      store.unpinNetwork('a');

      expect(store.pinnedIds).toEqual(['b']);
    });

    it('is a no-op when unpinNetwork is called for an id that is not pinned', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      store.pinNetwork('a');
      store.unpinNetwork('x');

      expect(store.pinnedIds).toEqual(['a']);
    });

    it('returns pinnedIds as a reactive snapshot via the singleton', () => {
      expect(Array.isArray(chatStore.pinnedIds)).toBe(true);
    });
  });

  describe('reset()', () => {
    it('clears messages and pinnedIds after a send', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      store.pinNetwork('net_a');
      store.pinNetwork('net_b');

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.messages.length).toBeGreaterThan(0);
      expect(store.pinnedIds).toEqual(['net_a', 'net_b']);

      store.reset();

      expect(store.messages).toEqual([]);
      expect(store.pinnedIds).toEqual([]);
    });

    it('clears messages and pinnedIds from idle state', () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      store.pinNetwork('x');

      store.reset();

      expect(store.messages).toEqual([]);
      expect(store.pinnedIds).toEqual([]);
      expect(store.status).toBe('idle');
      expect(store.error).toBeNull();
      expect(store.model).toBeNull();
    });

    it('calls stop() so any in-flight stream is aborted', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      // Start a stream that stays open
      fetchMock.mockImplementation((_url: string, options: RequestInit) => {
        const signal = options.signal as AbortSignal;
        const body = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(
                makeSSEBlock('RunStarted', { run_id: 'run_reset', model: 'm' }),
              ),
            );
            signal.addEventListener('abort', () => {
              controller.error(new DOMException('aborted', 'AbortError'));
            });
          },
        });
        return Promise.resolve({ ok: true, status: 200, body });
      });

      const promise = store.send('Hi', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      await vi.waitFor(() => {
        expect(store.status).toBe('streaming');
      });

      store.reset();

      await promise;

      expect(store.messages).toEqual([]);
      expect(store.pinnedIds).toEqual([]);
      expect(store.status).toBe('done');
      expect(store.error).toBeNull();
      expect(store.model).toBeNull();
    });

    it('resets status, error, and model when called from error state', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Server broke'));

      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      });

      expect(store.status).toBe('error');
      expect(store.error).toBe('Server broke');

      store.reset();

      expect(store.messages).toEqual([]);
      expect(store.pinnedIds).toEqual([]);
      expect(store.status).toBe('idle');
      expect(store.error).toBeNull();
      expect(store.model).toBeNull();
    });
  });

  describe('send() includes context + pinned ids', () => {
    it('includes active_network_id and active_network_name in the fetch body', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('Hello', {
        active_network_id: 'net_42',
        active_network_name: 'My Network',
        pinned_network_ids: [],
      });

      const fetchCall = fetchMock.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(fetchCall[1].body as string);
      expect(body.context.active_network_id).toBe('net_42');
      expect(body.context.active_network_name).toBe('My Network');
    });

    it('sends pinned_network_ids from the store, not from the caller context', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      store.pinNetwork('pinned_a');
      store.pinNetwork('pinned_b');

      await store.send('Hello', {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: ['caller_pinned'],
      });

      const fetchCall = fetchMock.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(fetchCall[1].body as string);
      expect(body.context.pinned_network_ids).toEqual(['pinned_a', 'pinned_b']);
    });

    it('includes chat context and messages in the fetch request body', async () => {
      const ChatStoreClass = Object.getPrototypeOf(chatStore).constructor;
      const store = new ChatStoreClass() as typeof chatStore;

      await store.send('First', {
        active_network_id: 'net_1',
        active_network_name: 'Net One',
        pinned_network_ids: [],
      });

      // The fetch body should contain the user message and context
      const firstCall = fetchMock.mock.calls[0] as [string, RequestInit];
      const firstBody = JSON.parse(firstCall[1].body as string);
      expect(firstBody.messages).toHaveLength(1);
      expect(firstBody.context.active_network_id).toBe('net_1');
      expect(firstBody.context.active_network_name).toBe('Net One');
    });
  });

  describe('ordered segments', () => {
    it('preserves the wire order: text → tool_call → text (GPT-style)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'r', model: 'gpt-4' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'a', delta: 'Let me check. ' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc', tool_name: 'list_networks' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 'tc', args: {} }) +
                makeSSEBlock('ToolCallResult', {
                  tool_call_id: 'tc',
                  result: { ok: true },
                  is_error: false,
                  error: null,
                }) +
                makeSSEBlock('TextMessageContent', { message_id: 'b', delta: 'You have 1 network.' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValue({ ok: true, status: 200, body });
      const store = new (Object.getPrototypeOf(chatStore).constructor)() as typeof chatStore;
      await store.send('list', { active_network_id: null, active_network_name: null, pinned_network_ids: [] });
      const a = store.messages[1] as AssistantMessage;
      expect(a.segments.map((s) => s.kind)).toEqual(['text', 'tool_call', 'text']);
      expect((a.segments[0] as { text: string }).text).toBe('Let me check. ');
      expect((a.segments[2] as { text: string }).text).toBe('You have 1 network.');
    });

    it('preserves order when the tool call is emitted before any text (reasoning-first models)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'r', model: 'qwen' }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'a', delta: 'thinking...' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 'tc', tool_name: 'list_networks' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 'tc', args: {} }) +
                makeSSEBlock('ToolCallResult', { tool_call_id: 'tc', result: {}, is_error: false, error: null }) +
                makeSSEBlock('TextMessageContent', { message_id: 'b', delta: 'Answer.' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValue({ ok: true, status: 200, body });
      const store = new (Object.getPrototypeOf(chatStore).constructor)() as typeof chatStore;
      await store.send('q', { active_network_id: null, active_network_name: null, pinned_network_ids: [] });
      const a = store.messages[1] as AssistantMessage;
      expect(reasoningOf(a)).toBe('thinking...');
      expect(a.segments.map((s) => s.kind)).toEqual(['reasoning', 'tool_call', 'text']);
    });

    it('interleaves multiple reasoning chunks with tool calls in wire order', async () => {
      // Models like qwen emit: reasoning_A → tool_1 → reasoning_B → tool_2 → reasoning_C → text.
      // Each LLM iteration uses a new message_id, so reasoning chunks remain
      // separate segments anchored at their call site.
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'r', model: 'qwen' }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'A', delta: 'pick tool 1' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 't1', tool_name: 'list_networks' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 't1', args: {} }) +
                makeSSEBlock('ToolCallResult', { tool_call_id: 't1', result: {}, is_error: false, error: null }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'B', delta: 'pick tool 2' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 't2', tool_name: 'get_network_detail' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 't2', args: {} }) +
                makeSSEBlock('ToolCallResult', { tool_call_id: 't2', result: {}, is_error: false, error: null }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'C', delta: 'compose answer' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'C', delta: 'Done.' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValue({ ok: true, status: 200, body });
      const store = new (Object.getPrototypeOf(chatStore).constructor)() as typeof chatStore;
      await store.send('q', { active_network_id: null, active_network_name: null, pinned_network_ids: [] });
      const a = store.messages[1] as AssistantMessage;
      expect(a.segments.map((s) => s.kind)).toEqual([
        'reasoning', 'tool_call',
        'reasoning', 'tool_call',
        'reasoning', 'text',
      ]);
    });

    it('coalesces consecutive TextMessageContent deltas with the same message_id', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'r', model: 'm' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'a', delta: 'Hello' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'a', delta: ', world' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValue({ ok: true, status: 200, body });
      const store = new (Object.getPrototypeOf(chatStore).constructor)() as typeof chatStore;
      await store.send('q', { active_network_id: null, active_network_name: null, pinned_network_ids: [] });
      const a = store.messages[1] as AssistantMessage;
      expect(a.segments).toHaveLength(1);
      expect((a.segments[0] as { text: string }).text).toBe('Hello, world');
    });

    it('starts a new text segment when message_id changes (multi-iteration turn)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'r', model: 'm' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'a', delta: 'first' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'b', delta: 'second' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValue({ ok: true, status: 200, body });
      const store = new (Object.getPrototypeOf(chatStore).constructor)() as typeof chatStore;
      await store.send('q', { active_network_id: null, active_network_name: null, pinned_network_ids: [] });
      const a = store.messages[1] as AssistantMessage;
      expect(a.segments).toHaveLength(2);
      expect((a.segments[0] as { text: string }).text).toBe('first');
      expect((a.segments[1] as { text: string }).text).toBe('second');
    });

    it('tags ToolCallSegment.phase=reasoning when the last delta was reasoning', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'r', model: 'qwen' }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'a', delta: 'think' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 't1', tool_name: 'list_networks' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValue({ ok: true, status: 200, body });
      const store = new (Object.getPrototypeOf(chatStore).constructor)() as typeof chatStore;
      await store.send('q', { active_network_id: null, active_network_name: null, pinned_network_ids: [] });
      const a = store.messages[1] as AssistantMessage;
      const tc = a.segments.find((s) => s.kind === 'tool_call') as ToolCallSegment;
      expect(tc.phase).toBe('reasoning');
    });

    it('tags ToolCallSegment.phase=content when the last delta was text (non-reasoning model)', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'r', model: 'gpt-3.5' }) +
                makeSSEBlock('TextMessageContent', { message_id: 'a', delta: 'Let me check.' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 't1', tool_name: 'list_networks' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValue({ ok: true, status: 200, body });
      const store = new (Object.getPrototypeOf(chatStore).constructor)() as typeof chatStore;
      await store.send('q', { active_network_id: null, active_network_name: null, pinned_network_ids: [] });
      const a = store.messages[1] as AssistantMessage;
      const tc = a.segments.find((s) => s.kind === 'tool_call') as ToolCallSegment;
      expect(tc.phase).toBe('content');
    });

    it('supports mixed turns: some tool calls in reasoning, others in content', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              makeSSEBlock('RunStarted', { run_id: 'r', model: 'mixed' }) +
                makeSSEBlock('ReasoningMessageContent', { message_id: 'a', delta: 'plan' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 't1', tool_name: 'list_networks' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 't1', args: {} }) +
                makeSSEBlock('ToolCallResult', { tool_call_id: 't1', result: {}, is_error: false, error: null }) +
                makeSSEBlock('TextMessageContent', { message_id: 'b', delta: 'Now let me look up details.' }) +
                makeSSEBlock('ToolCallStart', { tool_call_id: 't2', tool_name: 'get_network_detail' }) +
                makeSSEBlock('ToolCallEnd', { tool_call_id: 't2', args: {} }) +
                makeSSEBlock('ToolCallResult', { tool_call_id: 't2', result: {}, is_error: false, error: null }) +
                makeSSEBlock('TextMessageContent', { message_id: 'b', delta: ' Done.' }),
            ),
          );
          controller.close();
        },
      });
      fetchMock.mockResolvedValue({ ok: true, status: 200, body });
      const store = new (Object.getPrototypeOf(chatStore).constructor)() as typeof chatStore;
      await store.send('q', { active_network_id: null, active_network_name: null, pinned_network_ids: [] });
      const a = store.messages[1] as AssistantMessage;
      const calls = a.segments.filter((s) => s.kind === 'tool_call') as ToolCallSegment[];
      expect(calls.map((c) => c.phase)).toEqual(['reasoning', 'content']);
    });
  });
});
