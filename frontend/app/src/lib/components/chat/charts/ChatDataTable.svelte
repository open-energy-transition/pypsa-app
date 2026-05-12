<script lang="ts">
  import {
    createTable,
    getCoreRowModel,
  } from '@tanstack/svelte-table';
  import * as Table from '$lib/components/ui/table';
  import FlexRender from '$lib/components/ui/data-table/flex-render.svelte';

  let { data }: {
    data: { columns: string[]; rows: unknown[][] };
  } = $props();

  const columns = $derived(data.columns ?? []);
  const rows = $derived(data.rows ?? []);

  const columnDefs = $derived(
    columns.map((col, i) => ({
      accessorKey: String(i),
      header: col,
      cell: (info: { getValue: () => unknown }) => {
        const val = info.getValue();
        return val === null || val === undefined ? '' : String(val);
      },
    }))
  );

  const tableData = $derived(
    rows.map((row) => {
      const obj: Record<string, unknown> = {};
      columns.forEach((_, i) => {
        obj[String(i)] = row[i];
      });
      return obj;
    })
  );

  const table = createTable<Record<string, unknown>>({
    get data() {
      return tableData;
    },
    get columns() {
      return columnDefs;
    },
    getCoreRowModel: getCoreRowModel(),
  });
</script>

{#if columns.length > 0}
  <div class="overflow-auto max-h-80 rounded-md border border-border">
    <Table.Root>
      <Table.Header>
        {#each table.getHeaderGroups() as headerGroup}
          <Table.Row>
            {#each headerGroup.headers as header}
              <Table.Head class="px-2 py-1 text-xs font-medium text-muted-foreground bg-muted/50">
                {#if !header.isPlaceholder}
                  <FlexRender
                    content={header.column.columnDef.header as never}
                    context={header.getContext() as never}
                  />
                {/if}
              </Table.Head>
            {/each}
          </Table.Row>
        {/each}
      </Table.Header>
      <Table.Body>
        {#each table.getRowModel().rows as row}
          <Table.Row class="border-b border-border">
            {#each row.getVisibleCells() as cell}
              <Table.Cell class="px-2 py-1 text-xs">
                <FlexRender
                  content={cell.column.columnDef.cell as never}
                  context={cell.getContext() as never}
                />
              </Table.Cell>
            {/each}
          </Table.Row>
        {/each}
      </Table.Body>
    </Table.Root>
  </div>
{:else}
  <p class="text-xs text-muted-foreground italic">No data available.</p>
{/if}
