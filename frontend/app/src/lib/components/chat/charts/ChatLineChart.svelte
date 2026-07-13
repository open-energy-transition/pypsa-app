<script lang="ts">
  import { onMount } from 'svelte';
  let { spec, data }: {
    spec: { x: string; y: string; title?: string };
    data: { columns: string[]; rows: unknown[][] };
  } = $props();
  let el = $state<HTMLDivElement>();
  let error = $state<string>();

  onMount(async () => {
    try {
      const Plotly = (await import('plotly.js-dist')).default;
      const xi = data.columns.indexOf(spec.x);
      const yi = data.columns.indexOf(spec.y);
      const xs = data.rows.map((r) => r[xi]);
      const ys = data.rows.map((r) => r[yi]);
      Plotly.newPlot(el!, [{ type: 'line', x: xs, y: ys }], {
        title: spec.title,
        margin: { t: 28, r: 12, b: 36, l: 40 },
        height: 240,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { size: 11 },
      }, { displayModeBar: false, responsive: true });
    } catch {
      error = 'Chart rendering failed';
    }
  });
</script>

{#if error}
  <div class="w-full text-xs text-destructive">{error}</div>
{:else}
  <div bind:this={el} class="w-full"></div>
{/if}
