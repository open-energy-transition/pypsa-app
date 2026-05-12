export type Role = 'user' | 'assistant' | 'tool';

export interface ToolCall {
  id: string;
  name: string;
  args_partial: string; // streamed JSON fragment buffer
  args?: Record<string, unknown>; // populated when ToolCallEnd arrives
  status: 'streaming' | 'running' | 'complete' | 'error';
}

export interface ToolResult {
  tool_call_id: string;
  result: unknown | null; // tool payload (e.g. { summary, data, display_hint, chart_spec })
  is_error: boolean;
  error: string | null;
}

export interface UserMessage {
  id: string; // UUID; client-generated
  role: 'user';
  content: string;
  timestamp: string; // ISO-8601
}

export interface TextSegment {
  kind: 'text';
  message_id: string;
  text: string;
}

export interface ReasoningSegment {
  kind: 'reasoning';
  message_id: string;
  text: string;
}

export interface ToolCallSegment {
  kind: 'tool_call';
  id: string;
  name: string;
  args_partial: string;
  args?: Record<string, unknown>;
  status: 'streaming' | 'running' | 'complete' | 'error';
  result?: ToolResult;
  phase: 'reasoning' | 'content';
}

export type AssistantSegment = TextSegment | ReasoningSegment | ToolCallSegment;

export interface AssistantMessage {
  id: string;
  role: 'assistant';
  segments: AssistantSegment[];
  timestamp: string;
}

export type Message = UserMessage | AssistantMessage;

export interface ChatContext {
  active_network_id: string | null;
  active_network_name: string | null;
  pinned_network_ids: string[];
}

export type AGUIEvent =
  | { event: 'RunStarted'; data: { run_id: string; model: string } }
  | { event: 'TextMessageContent'; data: { message_id: string; delta: string } }
  | { event: 'ReasoningMessageContent'; data: { message_id: string; delta: string } }
  | { event: 'ToolCallStart'; data: { tool_call_id: string; tool_name: string } }
  | { event: 'ToolCallArgs'; data: { tool_call_id: string; delta: string } }
  | { event: 'ToolCallEnd'; data: { tool_call_id: string; args: Record<string, unknown> } }
  | { event: 'ToolCallResult'; data: ToolResult }
  | { event: 'RunFinished'; data: { run_id: string; usage: { input_tokens: number; output_tokens: number }; stop_reason: string } }
  | { event: 'RunError'; data: { run_id: string; code: string; message: string } };
