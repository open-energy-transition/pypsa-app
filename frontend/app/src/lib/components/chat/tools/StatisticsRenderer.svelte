<script lang="ts">
  import ChatBarChart from '../charts/ChatBarChart.svelte'
  import ChatLineChart from '../charts/ChatLineChart.svelte'
  import ChatPieChart from '../charts/ChatPieChart.svelte'
  import ChatDataTable from '../charts/ChatDataTable.svelte'
  import { untrack } from 'svelte'

  let { args = {}, result }: {
    args?: Record<string, unknown>
    result: {
      summary?: string
      data?: { columns?: string[]; rows?: unknown[][] }
      display_hint?: 'chart' | 'table'
      chart_spec?: { type: string; x: string; y: string; title?: string }
    } | null
  } = $props()

  let view = $state<'chart' | 'table'>(untrack(() => result?.display_hint ?? 'table'))

  const chartData = $derived<{ columns: string[]; rows: unknown[][] }>({
    columns: result?.data?.columns ?? [],
    rows: result?.data?.rows ?? [],
  })
</script>

{#if result}
  <div class="space-y-2">
    {#if result.summary}
      <p class="text-sm">{result.summary}</p>
    {/if}

    <div class="flex gap-2 text-xs">
      <button class:underline={view === 'chart'} aria-pressed={view === 'chart'} onclick={() => (view = 'chart')}>Chart</button>
      <button class:underline={view === 'table'} aria-pressed={view === 'table'} onclick={() => (view = 'table')}>Table</button>
    </div>

    {#if view === 'chart' && result.chart_spec}
      {#if result.chart_spec.type === 'bar'}
        <ChatBarChart spec={result.chart_spec} data={chartData} />
      {:else if result.chart_spec.type === 'line'}
        <ChatLineChart spec={result.chart_spec} data={chartData} />
      {:else if result.chart_spec.type === 'pie'}
        <ChatPieChart spec={result.chart_spec} data={chartData} />
      {:else}
        <ChatDataTable data={chartData} />
      {/if}
    {:else}
      <ChatDataTable data={chartData} />
    {/if}
  </div>
{/if}
