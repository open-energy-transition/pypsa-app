import { describe, it, expect } from 'vitest'
import { compile } from 'svelte/compiler'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(__dirname, 'StatisticsRenderer.svelte'), 'utf-8')

describe('StatisticsRenderer', () => {
  it('compiles without errors', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toBeTruthy()
    expect(result.js.code.length).toBeGreaterThan(0)
  })

  it('accepts args and result props via $props() rune', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/\$props/)
    expect(result.js.code).toMatch(/args/)
    expect(result.js.code).toMatch(/result/)
  })

  it('renders result.summary in a text-sm paragraph', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/result\.summary/)
    expect(result.js.code).toMatch(/text-sm/)
  })

  it('has a view toggle with Chart and Table buttons', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    const code = result.js.code
    expect(code).toMatch(/Chart/)
    expect(code).toMatch(/Table/)
  })

  it('uses $state for view tracking initialized from result.display_hint', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/\.state\(/)
    expect(result.js.code).toMatch(/display_hint/)
  })

  it('defaults view to table when display_hint is missing', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/['"]table['"]/)
  })

  it('toggles between chart and table views via button clicks', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/set\(view.*chart/)
    expect(result.js.code).toMatch(/set\(view.*table/)
  })

  it('underlines the active toggle button', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/underline/)
  })

  it('marks active toggle button with aria-pressed', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/aria-pressed/)
  })

  it('imports ChatBarChart for bar chart rendering', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/ChatBarChart/)
  })

  it('imports ChatLineChart for line chart rendering', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/ChatLineChart/)
  })

  it('imports ChatPieChart for pie chart rendering', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/ChatPieChart/)
  })

  it('imports ChatDataTable for table view rendering', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/ChatDataTable/)
  })

  it('renders appropriate chart component based on chart_spec.type', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/chart_spec/)
    expect(result.js.code).toMatch(/type/)
    expect(result.js.code).toMatch(/bar/)
    expect(result.js.code).toMatch(/line/)
    expect(result.js.code).toMatch(/pie/)
  })

  it('renders ChatDataTable when view is table', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/ChatDataTable/)
  })

  it('passes chartData to ChatDataTable as the data prop', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/ChatDataTable/)
    expect(result.js.code).toMatch(/chartData/)
    expect(result.js.code).toMatch(/get data\(\)/)
    expect(result.js.code).toMatch(/get\(chartData\)/)
  })

  it('derives chartData columns and rows from result.data with null-safe defaults', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/columns.*\?\?/)
    expect(result.js.code).toMatch(/rows.*\?\?/)
  })

  it('uses outer container with space-y-2 class', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/space-y-2/)
  })

  it('uses flex gap-2 text-xs for toggle button container', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/flex/)
    expect(result.js.code).toMatch(/gap-2/)
  })

  it('passes spec and data props to chart components', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    expect(result.js.code).toMatch(/result\.chart_spec/)
    expect(result.js.code).toMatch(/chartData/)
  })

  it('renders ChatDataTable as fallback when chart_spec.type is unknown', () => {
    const result = compile(source, {
      filename: 'StatisticsRenderer.svelte',
      generate: 'client',
    })
    const componentCalls = (result.js.code.match(/ChatDataTable\(/g) || []).length
    expect(componentCalls).toBeGreaterThanOrEqual(2)
  })
})
