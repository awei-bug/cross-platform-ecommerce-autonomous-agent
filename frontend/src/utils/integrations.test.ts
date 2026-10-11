import { describe, expect, it } from 'vitest'

import { formatConnectorTime, getConnectorStateDisplay, isConnectorReady } from './integrations'
import type { ConnectorState } from '../types/api'

const STATES: ConnectorState[] = [
  'credentials_required',
  'authorization_required',
  'adapter_pending',
  'ready',
  'expired',
  'revoked',
  'error',
]

describe('connector state display', () => {
  it('covers every state returned by the connector registry', () => {
    for (const state of STATES) {
      const display = getConnectorStateDisplay(state)
      expect(display.label, state).toBeTruthy()
      expect(['success', 'warning', 'danger', 'info'], state).toContain(display.tag)
    }
  })

  it('only drives re-authorization when the platform can accept it', () => {
    expect(getConnectorStateDisplay('authorization_required').action).toBe('authorize')
    expect(getConnectorStateDisplay('expired').action).toBe('reauthorize')
    expect(getConnectorStateDisplay('ready').action).toBe('none')
    expect(getConnectorStateDisplay('credentials_required').action).toBe('none')
  })

  it('treats authorization_required as not connected', () => {
    expect(isConnectorReady('ready')).toBe(true)
    expect(isConnectorReady('authorization_required')).toBe(false)
  })
})

describe('connector time formatting', () => {
  it('renders ISO timestamps in a stable local format', () => {
    expect(formatConnectorTime('2026-10-10T08:05:00Z')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
  })

  it('never shows an invalid placeholder date for missing values', () => {
    expect(formatConnectorTime(null)).toBe('—')
    expect(formatConnectorTime(undefined)).toBe('—')
    expect(formatConnectorTime('not-a-date')).toBe('—')
  })
})
