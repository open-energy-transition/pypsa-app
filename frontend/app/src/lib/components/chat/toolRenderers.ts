import type { Component } from 'svelte';
import StatisticsRenderer from './tools/StatisticsRenderer.svelte';
import NetworksTableRenderer from './tools/NetworksTableRenderer.svelte';
import NetworkCardRenderer from './tools/NetworkCardRenderer.svelte';

type RendererProps = { args?: Record<string, unknown>; result: unknown };

export const toolRenderers: Record<string, Component<RendererProps>> = {
  get_network_statistics: StatisticsRenderer as Component<RendererProps>,
  list_networks: NetworksTableRenderer as Component<RendererProps>,
  get_network_detail: NetworkCardRenderer as Component<RendererProps>,
};
