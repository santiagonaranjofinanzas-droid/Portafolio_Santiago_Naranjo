'use client'

import { useEffect, useState } from 'react'
import { buildApiUrl } from '@/lib/api'

interface MT5StatusIndicatorProps {
  compact?: boolean
  statisticalAlert?: string  null
  accountLogin?: string  null
  serverName?: string  null
}

interface MetricsTradeEntry {
  exittime?: string  number
  exit_time?: string  number
}

interface MetricsResponse {
  history?: MetricsTradeEntry[]
  account_snapshot?: {
    captured_at?: string  number
  }
}

function parseTimestampSeconds(raw: string  number  undefined): number  null {
  if (raw === undefined  raw === null) return null
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw)) return null
    return raw > 1e12 ? raw / 1000 : raw
  }
  const text = String(raw).trim()
  if (!text) return null
  const numeric = Number(text)
  if (Number.isFinite(numeric)) return numeric > 1e12 ? numeric / 1000 : numeric
  const hasTimezone = /(?:Z[+-]\d{2}:?\d{2})$/i.test(text)
  const normalizedIso = hasTimezone ? text : `${text}Z`
  const ms = Date.parse(normalizedIso)
  return Number.isFinite(ms) ? ms / 1000 : null
}

function isFreshSnapshot(capturedAt: string  number  undefined, maxAgeSeconds = 300): boolean {
  const ts = parseTimestampSeconds(capturedAt)
  if (ts === null) return false
  return (Date.now() / 1000) - ts <= maxAgeSeconds
}

function formatElapsed(secondsDiff: number): string {
  const sec = Math.max(0, Math.floor(secondsDiff))
  const totalMinutes = Math.floor(sec / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${totalMinutes}m`
}

export default function MT5StatusIndicator({ 
  compact = false, 
  statisticalAlert = null,
  accountLogin = null,
  serverName = null
}: MT5StatusIndicatorProps) {
  const [status, setStatus] = useState<'connected'  'listening'  'idle'  'error'>('idle')
  const [lastTradeTime, setLastTradeTime] = useState<string  null>(null)

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const queryParams: Record<string, string> = {}
        if (accountLogin) queryParams.account_login = accountLogin
        if (serverName) queryParams.server_name = serverName
        
        const response = await fetch(buildApiUrl('/metrics', queryParams))
        if (!response.ok) { setStatus('error'); return }
        const data = (await response.json()) as MetricsResponse
        const now = Date.now() / 1000
        let mostRecentTime: number  null = null
        if (Array.isArray(data.history)) {
          data.history.forEach((trade) => {
            const rawExit = trade.exittime  trade.exit_time
            const parsedTs = parseTimestampSeconds(rawExit)
            const exitTs = parsedTs !== null ? Math.min(parsedTs, now) : null
            if (exitTs !== null && (mostRecentTime === null  exitTs > mostRecentTime)) mostRecentTime = exitTs
          })
        }
        const snapshotFresh = isFreshSnapshot(data.account_snapshot?.captured_at)
        if (mostRecentTime !== null) {
          const seconds = Math.floor(now - mostRecentTime)
          setLastTradeTime(formatElapsed(seconds))
          setStatus(seconds < 300 ? 'connected' : 'listening')
        } else if (snapshotFresh) {
          setStatus('connected')
          setLastTradeTime('0m')
        } else { setStatus('idle'); setLastTradeTime(null) }
      } catch { setStatus('error') }
    }
    checkStatus()
    const interval = setInterval(checkStatus, 30000)
    return () => clearInterval(interval)
  }, [accountLogin, serverName])

  const statusLabels = { connected: 'MT5 Activo', listening: 'MT5 Inactivo', idle: 'MT5 Desconectado', error: 'Error' }
  const dotClass = status === 'connected' ? 'status-dot--ok' : status === 'listening' ? 'status-dot--warn' : status === 'error' ? 'status-dot--error' : 'status-dot--idle'

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <div className={`status-dot ${dotClass}`} />
        <span className="text-[10px] font-data font-medium" style={{ color: 'var(--text-muted)' }}>{statusLabels[status]}</span>
        {lastTradeTime && <span className="text-[10px] font-data" style={{ color: 'var(--text-ghost)' }}>· {lastTradeTime}</span>}
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 rounded-lg" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--bg-border)' }}>
      <div className="flex items-center gap-3">
        <div className={`status-dot ${dotClass}`} />
        <div>
          <p className="text-xs font-bold" style={{ color: 'var(--text-secondary)' }}>{statusLabels[status]}</p>
          {lastTradeTime && <p className="text-[10px] font-data" style={{ color: 'var(--text-muted)' }}>Último trade: hace {lastTradeTime}</p>}
        </div>
      </div>
      {statisticalAlert && (
        <div className="ops-badge ops-badge--warn text-[9px]">{statisticalAlert}</div>
      )}
    </div>
  )
}
