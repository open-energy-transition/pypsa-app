import { describe, it, expect } from 'vitest';
import type { Role, ToolCall, ToolResult, UserMessage, AssistantMessage, Message, ChatContext, AGUIEvent } from './chat';

describe('chat types', () => {
  describe('Role', () => {
    it('accepts "user"', () => {
      const role: Role = 'user';
      expect(role).toBe('user');
    });

    it('accepts "assistant"', () => {
      const role: Role = 'assistant';
      expect(role).toBe('assistant');
    });

    it('accepts "tool"', () => {
      const role: Role = 'tool';
      expect(role).toBe('tool');
    });
  });

  describe('ToolCall', () => {
    it('constructs a streaming tool call', () => {
      const tc: ToolCall = {
        id: 'call_abc',
        name: 'list_networks',
        args_partial: '{"owner":',
        status: 'streaming',
      };
      expect(tc.id).toBe('call_abc');
      expect(tc.name).toBe('list_networks');
      expect(tc.args_partial).toBe('{"owner":');
      expect(tc.status).toBe('streaming');
      expect(tc.args).toBeUndefined();
    });

    it('constructs a complete tool call with args', () => {
      const tc: ToolCall = {
        id: 'call_def',
        name: 'get_network_statistics',
        args_partial: '',
        args: { network_id: '42', statistic: 'capacity_by_carrier' },
        status: 'complete',
      };
      expect(tc.args).toEqual({ network_id: '42', statistic: 'capacity_by_carrier' });
      expect(tc.status).toBe('complete');
    });

    it('constructs a running tool call', () => {
      const tc: ToolCall = {
        id: 'call_ghi',
        name: 'get_network_detail',
        args_partial: '{"network_id": "1"}',
        args: { network_id: '1' },
        status: 'running',
      };
      expect(tc.status).toBe('running');
    });

    it('constructs an error tool call', () => {
      const tc: ToolCall = {
        id: 'call_err',
        name: 'bad_tool',
        args_partial: '',
        status: 'error',
      };
      expect(tc.status).toBe('error');
    });
  });

  describe('ToolResult', () => {
    it('constructs a successful result', () => {
      const tr: ToolResult = {
        tool_call_id: 'call_abc',
        result: { summary: '3 networks found', data: { columns: [], rows: [] } },
        is_error: false,
        error: null,
      };
      expect(tr.tool_call_id).toBe('call_abc');
      expect(tr.is_error).toBe(false);
      expect(tr.error).toBeNull();
      expect(tr.result).toEqual({
        summary: '3 networks found',
        data: { columns: [], rows: [] },
      });
    });

    it('constructs an error result', () => {
      const tr: ToolResult = {
        tool_call_id: 'call_err',
        result: null,
        is_error: true,
        error: 'tool not found',
      };
      expect(tr.is_error).toBe(true);
      expect(tr.error).toBe('tool not found');
      expect(tr.result).toBeNull();
    });

    it('constructs a result with null result for unknown tool', () => {
      const tr: ToolResult = {
        tool_call_id: 'call_unknown',
        result: null,
        is_error: true,
        error: 'unknown tool: xyz',
      };
      expect(tr.is_error).toBe(true);
      expect(tr.error).toBe('unknown tool: xyz');
    });
  });

  describe('Message', () => {
    it('constructs a user message', () => {
      const msg: UserMessage = {
        id: 'msg_1',
        role: 'user',
        content: 'List my networks',
        timestamp: '2026-05-05T10:00:00.000Z',
      };
      expect(msg.role).toBe('user');
      expect(msg.content).toBe('List my networks');
    });

    it('constructs an assistant message with reasoning', () => {
      const msg: AssistantMessage = {
        id: 'msg_2',
        role: 'assistant',
        content: 'Here are your networks.',
        reasoning: 'The user wants to see all networks...',
        timestamp: '2026-05-05T10:00:01.000Z',
      };
      expect(msg.role).toBe('assistant');
      expect(msg.content).toBe('Here are your networks.');
      expect(msg.reasoning).toBe('The user wants to see all networks...');
    });

    it('constructs an assistant message with tool calls', () => {
      const tc: ToolCall = {
        id: 'call_abc',
        name: 'list_networks',
        args_partial: '{}',
        args: {},
        status: 'complete',
      };
      const msg: AssistantMessage = {
        id: 'msg_3',
        role: 'assistant',
        content: '',
        tool_calls: [tc],
        timestamp: '2026-05-05T10:00:02.000Z',
      };
      expect(msg.tool_calls).toHaveLength(1);
      expect(msg.tool_calls![0].name).toBe('list_networks');
    });

    it('constructs an assistant message with tool results', () => {
      const tr: ToolResult = {
        tool_call_id: 'call_abc',
        result: { summary: 'done' },
        is_error: false,
        error: null,
      };
      const msg: AssistantMessage = {
        id: 'msg_4',
        role: 'assistant',
        content: '',
        tool_results: [tr],
        timestamp: '2026-05-05T10:00:03.000Z',
      };
      expect(msg.tool_results).toHaveLength(1);
      expect(msg.tool_results![0].is_error).toBe(false);
    });

    it('narrowing Message by role grants access to assistant-only fields', () => {
      const msg: Message = {
        id: 'msg_narrow',
        role: 'assistant',
        content: 'result',
        reasoning: 'thinking...',
        tool_calls: [{ id: 'tc1', name: 'list_networks', args_partial: '', args: {}, status: 'complete' }],
        tool_results: [{ tool_call_id: 'tc1', result: null, is_error: false, error: null }],
        timestamp: '2026-05-05T10:00:00.000Z',
      };
      if (msg.role === 'assistant') {
        expect(msg.reasoning).toBe('thinking...');
        expect(msg.tool_calls).toHaveLength(1);
        expect(msg.tool_results).toHaveLength(1);
      }
    });

    it('requires an id field', () => {
      const msg: UserMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: 'hi',
        timestamp: new Date().toISOString(),
      };
      expect(msg.id).toBeTruthy();
      expect(typeof msg.id).toBe('string');
    });

    it('requires a timestamp field in ISO-8601 format', () => {
      const msg: UserMessage = {
        id: 'msg_ts',
        role: 'user',
        content: 'hi',
        timestamp: '2026-05-05T10:00:00.000Z',
      };
      expect(msg.timestamp).toBe('2026-05-05T10:00:00.000Z');
    });

    it('constructs a full assistant message with tool calls and results', () => {
      const tc: ToolCall = {
        id: 'call_full',
        name: 'get_network_statistics',
        args_partial: '{"network_id":"1","statistic":"capacity_by_carrier"}',
        args: { network_id: '1', statistic: 'capacity_by_carrier' },
        status: 'complete',
      };
      const tr: ToolResult = {
        tool_call_id: 'call_full',
        result: {
          summary: 'Total capacity: 1240 MW',
          data: { columns: ['carrier', 'capacity_mw'], rows: [['wind', 800], ['solar', 440]] },
          display_hint: 'chart',
          chart_spec: { type: 'bar', x: 'carrier', y: 'capacity_mw', title: 'Capacity by Carrier' },
        },
        is_error: false,
        error: null,
      };
      const msg: AssistantMessage = {
        id: 'msg_full',
        role: 'assistant',
        content: 'The network has 1240 MW of installed capacity across 2 carriers.',
        reasoning: 'Analyzing capacity breakdown...',
        tool_calls: [tc],
        tool_results: [tr],
        timestamp: '2026-05-05T10:00:05.000Z',
      };
      expect(msg.role).toBe('assistant');
      expect(msg.content).toBeTruthy();
      expect(msg.reasoning).toBeTruthy();
      expect(msg.tool_calls).toHaveLength(1);
      expect(msg.tool_results).toHaveLength(1);
      expect(msg.tool_results![0].tool_call_id).toBe(msg.tool_calls![0].id);
    });
  });

  describe('ChatContext', () => {
    it('constructs with active network id and name', () => {
      const ctx: ChatContext = {
        active_network_id: 'net_42',
        active_network_name: 'My Network',
        pinned_network_ids: [],
      };
      expect(ctx.active_network_id).toBe('net_42');
      expect(ctx.active_network_name).toBe('My Network');
      expect(ctx.pinned_network_ids).toEqual([]);
    });

    it('constructs with null active network and no pinned ids', () => {
      const ctx: ChatContext = {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: [],
      };
      expect(ctx.active_network_id).toBeNull();
      expect(ctx.active_network_name).toBeNull();
    });

    it('constructs with pinned network ids', () => {
      const ctx: ChatContext = {
        active_network_id: 'net_1',
        active_network_name: null,
        pinned_network_ids: ['net_2', 'net_3'],
      };
      expect(ctx.pinned_network_ids).toEqual(['net_2', 'net_3']);
    });

    it('requires pinned_network_ids to be string array', () => {
      const ctx: ChatContext = {
        active_network_id: null,
        active_network_name: null,
        pinned_network_ids: ['a', 'b', 'c'],
      };
      ctx.pinned_network_ids.forEach((id: string) => expect(typeof id).toBe('string'));
    });
  });

  describe('AGUIEvent', () => {
    it('constructs RunStarted event', () => {
      const ev: AGUIEvent = {
        event: 'RunStarted',
        data: { run_id: 'run_abc123', model: 'openai/qwen3.5:9b' },
      };
      expect(ev.event).toBe('RunStarted');
      expect(ev.data.run_id).toBe('run_abc123');
      expect(ev.data.model).toBe('openai/qwen3.5:9b');
    });

    it('constructs TextMessageContent event', () => {
      const ev: AGUIEvent = {
        event: 'TextMessageContent',
        data: { message_id: 'msg_1', delta: 'Hello' },
      };
      expect(ev.event).toBe('TextMessageContent');
      expect(ev.data.message_id).toBe('msg_1');
      expect(ev.data.delta).toBe('Hello');
    });

    it('constructs ReasoningMessageContent event', () => {
      const ev: AGUIEvent = {
        event: 'ReasoningMessageContent',
        data: { message_id: 'msg_2', delta: 'Analyzing...' },
      };
      expect(ev.event).toBe('ReasoningMessageContent');
      expect(ev.data.delta).toBe('Analyzing...');
    });

    it('constructs ToolCallStart event', () => {
      const ev: AGUIEvent = {
        event: 'ToolCallStart',
        data: { tool_call_id: 'call_42', tool_name: 'list_networks' },
      };
      expect(ev.event).toBe('ToolCallStart');
      expect(ev.data.tool_call_id).toBe('call_42');
      expect(ev.data.tool_name).toBe('list_networks');
    });

    it('constructs ToolCallArgs event', () => {
      const ev: AGUIEvent = {
        event: 'ToolCallArgs',
        data: { tool_call_id: 'call_42', delta: '{"limit":' },
      };
      expect(ev.event).toBe('ToolCallArgs');
      expect(ev.data.tool_call_id).toBe('call_42');
      expect(ev.data.delta).toBe('{"limit":');
    });

    it('constructs ToolCallEnd event', () => {
      const ev: AGUIEvent = {
        event: 'ToolCallEnd',
        data: { tool_call_id: 'call_42', args: { limit: 10 } },
      };
      expect(ev.event).toBe('ToolCallEnd');
      expect(ev.data.tool_call_id).toBe('call_42');
      expect(ev.data.args).toEqual({ limit: 10 });
    });

    it('constructs ToolCallResult event', () => {
      const ev: AGUIEvent = {
        event: 'ToolCallResult',
        data: {
          tool_call_id: 'call_42',
          result: { summary: 'found 3 networks' },
          is_error: false,
          error: null,
        },
      };
      expect(ev.event).toBe('ToolCallResult');
      expect(ev.data.tool_call_id).toBe('call_42');
      expect(ev.data.is_error).toBe(false);
      expect(ev.data.result).toEqual({ summary: 'found 3 networks' });
    });

    it('constructs RunFinished event', () => {
      const ev: AGUIEvent = {
        event: 'RunFinished',
        data: {
          run_id: 'run_abc123',
          usage: { input_tokens: 150, output_tokens: 80 },
          stop_reason: 'end_turn',
        },
      };
      expect(ev.event).toBe('RunFinished');
      expect(ev.data.usage.input_tokens).toBe(150);
      expect(ev.data.usage.output_tokens).toBe(80);
      expect(ev.data.stop_reason).toBe('end_turn');
    });

    it('constructs RunError event', () => {
      const ev: AGUIEvent = {
        event: 'RunError',
        data: { run_id: 'run_abc123', code: 'provider_timeout', message: 'LLM timed out' },
      };
      expect(ev.event).toBe('RunError');
      expect(ev.data.code).toBe('provider_timeout');
      expect(ev.data.message).toBe('LLM timed out');
    });

    it('narrows by event discriminator', () => {
      const ev: AGUIEvent = {
        event: 'TextMessageContent',
        data: { message_id: 'msg_n', delta: 'token' },
      };
      if (ev.event === 'TextMessageContent') {
        expect(ev.data.delta).toBe('token');
      }
    });

    it('narrows ToolCallResult event', () => {
      const ev: AGUIEvent = {
        event: 'ToolCallResult',
        data: { tool_call_id: 'call_err', result: null, is_error: true, error: 'failed' },
      };
      if (ev.event === 'ToolCallResult') {
        expect(ev.data.is_error).toBe(true);
        expect(ev.data.error).toBe('failed');
      }
    });
  });
});
