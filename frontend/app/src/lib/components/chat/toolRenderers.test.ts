import { describe, it, expect } from 'vitest'
import { toolRenderers } from './toolRenderers'

describe('toolRenderers', () => {
  it('registers get_network_statistics → StatisticsRenderer for the table/chart toggle view', () => {
    const renderer = toolRenderers['get_network_statistics']
    expect(renderer).toBeDefined()
    expect(typeof renderer).toBe('function')
  })

  it('registers list_networks → NetworksTableRenderer', () => {
    const renderer = toolRenderers['list_networks']
    expect(renderer).toBeDefined()
    expect(typeof renderer).toBe('function')
  })

  it('registers get_network_detail → NetworkCardRenderer', () => {
    const renderer = toolRenderers['get_network_detail']
    expect(renderer).toBeDefined()
    expect(typeof renderer).toBe('function')
  })

  it('returns undefined for unregistered tool names', () => {
    expect(toolRenderers['unknown_tool']).toBeUndefined()
  })
})
