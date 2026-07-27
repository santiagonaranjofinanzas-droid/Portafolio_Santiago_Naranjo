'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useMetrics, useLivePositions } from '@/hooks/useMetrics'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity,
  ArrowLeft,
  Building2,
  CandlestickChart,
  CircleAlert,
  Clock3,
  Gauge,
  Landmark,
  Layers3,
  ListFilter,
  Shield,
  Sparkles,
  RefreshCw,
  Smartphone,
  TrendingUp,
  Zap,
} from 'lucide-react'
import { clsx } from 'clsx'
import { buildApiUrl } from '@/lib/api'

type Trade = {
  symbol: string
  entrytime: string
  direction: 'Buy'  'Sell'
  netpnl: number
  r_multiple: number
  bot_id?: number  null
}

type LivePosition = {
  ticket?: number
  symbol?: string
  type?: string  number
  volume?: number
  profit?: number
}

const TAB_ITEMS = [
  { key: 'overview', label: 'Resumen', icon: Smartphone },
  { key: 'trades', label: 'Operaciones', icon: Activity },
  { key: 'live', label: 'En vivo', icon: Zap },
] as const

function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function formatCurrency(value: number): string {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

function MiniKpi({
  label,
  value,
  positive,
  icon: Icon,
}: {
  label: string
  value: string
  positive?: boolean
  icon: React.ComponentType<{ className?: string }>
}) {
  return (
    <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-elevated)]/90 px-3 py-3 shadow-[0_12px_26px_rgba(0,0,0,0.16)]">
      <div className="mb-1 flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-[0.14em] font-black text-[var(--text-muted)]">{label}</p>
        <Icon className="h-3.5 w-3.5 text-[var(--text-ghost)]" />
      </div>
      <p
        className={clsx(
          'font-data text-base font-black',
          positive === undefined ? 'text-[var(--text-primary)]' : positive ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]',
        )}
      >
        {value}
      </p>
    </div>
  )
}

function MetricRow({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon: React.ComponentType<{ className?: string }>
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--bg-border)] bg-[var(--bg-elevated)]/70 px-3 py-2.5">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] p-1.5">
          <Icon className="h-3.5 w-3.5 text-[var(--c-info)]" />
        </div>
        <p className="truncate text-[11px] uppercase tracking-wider font-bold text-[var(--text-muted)]">{label}</p>
      </div>
      <p className="font-data text-xs font-bold text-[var(--text-primary)]">{value}</p>
    </div>
  )
}

export default function MobileDashboardPage() {
  const [tab, setTab] = useState<'overview'  'trades'  'live'>('overview')
  const [selectedBot, setSelectedBot] = useState<number  null>(null)

  const queryClient = useQueryClient()
  const { data: stats, isLoading, error } = useMetrics(365, selectedBot)
  const { data: liveData = [] } = useLivePositions()

  const netProfit = toNumber(stats?.summary?.net_profit)
  const startCap = toNumber(stats?.summary?.start_cap)
  const summaryNav = startCap + netProfit
  const globalNav = toNumber(stats?.account_snapshot?.balance, summaryNav)
  const navValue = selectedBot === null ? globalNav : summaryNav
  const sharpe = toNumber(stats?.summary?.sharpe)
  const sqn = toNumber(stats?.summary?.sqn)
  const winRate = toNumber(stats?.perf?.win_rate)
  const drawdown = Math.abs(toNumber(stats?.perf?.max_drawdown))
  const pf = toNumber(stats?.perf?.pf)
  const cagr = toNumber(stats?.perf?.cagr)

  const accountLogin = stats?.account_snapshot?.account_login
  const serverName = stats?.account_snapshot?.server_name
  const capturedAt = stats?.account_snapshot?.captured_at

  const formatBotLabel = (bot: number) => (bot === 0 ? 'Manual / Unknown (0)' : `Node ${bot}`)

  const syncMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(buildApiUrl('/sync'), { method: 'POST' })
      if (!res.ok) throw new Error('Sync Failed')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics'] })
      queryClient.invalidateQueries({ queryKey: ['live'] })
    },
  })

  const topTrades = useMemo(() => {
    const trades: Trade[] = stats?.history  []
    return [...trades]
      .sort((a, b) => new Date(b.entrytime).getTime() - new Date(a.entrytime).getTime())
      .slice(0, 20)
  }, [stats?.history])

    if (isLoading) {
    return (
      <main className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-4">
        <div className="rounded-2xl border border-[var(--bg-border)] bg-[var(--bg-elevated)] p-4 animate-pulse">
          <p className="text-xs uppercase tracking-[0.2em] font-bold text-[var(--text-muted)]">Cargando terminal móvil</p>
          <div className="h-2 mt-3 rounded bg-[var(--bg-hover)]" />
        </div>
      </main>
    )
  }

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[radial-gradient(circle_at_18%_-6%,rgba(75,163,199,0.26),transparent_42%),radial-gradient(circle_at_85%_0%,rgba(92,107,192,0.2),transparent_45%),linear-gradient(180deg,var(--bg-base)_0%,var(--bg-void)_100%)] text-[var(--text-primary)] pb-28">
      <div className="pointer-events-none absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] [background-size:28px_28px]" />

      <section className="sticky top-0 z-30 border-b border-[var(--bg-border)] bg-[color:var(--bg-base)]/90 backdrop-blur-xl">
        <div className="px-4 py-3 flex items-center justify-between gap-3">
            <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.18em] font-black text-[var(--c-info)]">Panel de control móvil</p>
            <h1 className="text-sm font-extrabold tracking-tight truncate">BLACK KNIGHT — Panel</h1>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--c-info)]"
            >
              <RefreshCw className={clsx('w-3 h-3', syncMutation.isPending && 'animate-spin')} />
              Sincronizar
            </button>
            <Link href="/" className="inline-flex items-center gap-1 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              <ArrowLeft className="w-3 h-3" />
              Vista completa
            </Link>
          </div>
        </div>
      </section>

      <section className="relative z-10 px-4 pt-4 space-y-3">
        {error ? (
          <div className="rounded-2xl border border-[var(--c-negative)]/20 bg-[var(--bg-elevated)]/95 p-4">
            <div className="flex items-center gap-2 text-[var(--c-negative)]">
              <CircleAlert className="w-4 h-4" />
              <p className="text-xs uppercase font-bold tracking-wider">Backend offline</p>
            </div>
            <p className="text-[11px] mt-2 text-[var(--text-muted)]">No hay conexión con el nodo API remoto.</p>
          </div>
        ) : (
          <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-elevated)]/80 px-3 py-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-[var(--c-positive)] animate-pulse" />
              <p className="text-[11px] uppercase tracking-wider font-bold text-[var(--c-positive)]">Conexión en vivo activa</p>
              </div>
            <div className="text-[10px] text-[var(--text-muted)] font-data">{liveData.length} pos.</div>
          </div>
        )}

        <div className="rounded-2xl border border-[var(--bg-border)] bg-[linear-gradient(140deg,rgba(75,163,199,0.18),rgba(18,18,18,0.08))] px-4 py-4 shadow-[0_18px_34px_rgba(0,0,0,0.22)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.15em] font-black text-[var(--c-info)]">Portfolio NAV</p>
              <p className="mt-1 font-data text-2xl font-black text-[var(--text-primary)]">{formatCurrency(navValue)}</p>
            </div>
            <div className={clsx('rounded-lg px-2 py-1 text-[10px] font-black uppercase tracking-wider', netProfit >= 0 ? 'bg-[var(--c-positive-dim)] text-[var(--c-positive)]' : 'bg-[var(--c-negative-dim)] text-[var(--c-negative)]')}>
              {netProfit >= 0 ? '+' : ''}{formatCurrency(netProfit)}
            </div>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2.5 text-[11px]">
            <div className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-elevated)]/65 px-2.5 py-2">
              <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--text-muted)]">Account</p>
              <p className="font-data font-bold text-[var(--text-secondary)] truncate">{accountLogin  'N/A'}</p>
            </div>
            <div className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-elevated)]/65 px-2.5 py-2">
              <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--text-muted)]">Server</p>
              <p className="font-data font-bold text-[var(--text-secondary)] truncate">{serverName  'N/A'}</p>
            </div>
          </div>

          {capturedAt && (
            <div className="mt-2 flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
              <Clock3 className="h-3 w-3" />
              Snapshot {new Date(capturedAt).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </div>
          )}
        </div>

        {stats?.available_bots && stats.available_bots.length > 0 && (
          <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-elevated)]/85 px-3 py-2.5 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[var(--text-secondary)] text-xs font-bold uppercase tracking-wider">
              <ListFilter className="w-3.5 h-3.5 text-[var(--c-info)]" /> Bot
            </div>
            <select
              className="bg-transparent text-xs font-bold text-[var(--text-primary)] outline-none max-w-[62%] truncate"
              value={selectedBot ?? ''}
              onChange={(e) => {
                if (e.target.value === '') {
                  setSelectedBot(null)
                  return
                }
                const parsed = Number(e.target.value)
                setSelectedBot(Number.isFinite(parsed) ? parsed : null)
              }}
            >
              <option value="" className="bg-[var(--bg-elevated)]">Global Portfolio</option>
              {stats.available_bots.map((b: number) => (
                <option key={b} value={b} className="bg-[var(--bg-elevated)]">{formatBotLabel(b)}</option>
              ))}
            </select>
          </div>
        )}
      </section>

      <AnimatePresence mode="wait">
        {tab === 'overview' && (
          <motion.section
            key="overview"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.16 }}
            className="relative z-10 px-4 mt-3 space-y-3"
          >
            <div className="grid grid-cols-2 gap-3">
              <MiniKpi label="SQN" icon={Activity} value={sqn.toFixed(2)} />
              <MiniKpi label="Sharpe" icon={Zap} value={sharpe.toFixed(2)} />
              <MiniKpi label="Win Rate" icon={CandlestickChart} value={formatPct(winRate)} positive={winRate >= 0.5} />
              <MiniKpi label="Max DD" icon={Shield} value={formatPct(drawdown)} positive={drawdown <= 0.1} />
            </div>

            <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-elevated)]/90 p-3 space-y-2.5">
              <div className="flex items-center gap-2 mb-1">
                <Sparkles className="w-3.5 h-3.5 text-[var(--c-info)]" />
                <p className="text-[11px] uppercase tracking-[0.14em] font-black text-[var(--text-muted)]">Professional Snapshot</p>
              </div>
              <MetricRow label="Profit Factor" value={pf.toFixed(3)} icon={Gauge} />
              <MetricRow label="CAGR" value={formatPct(cagr)} icon={TrendingUp} />
              <MetricRow label="Capital Base" value={formatCurrency(startCap)} icon={Landmark} />
              <MetricRow label="Data Scope" value={selectedBot === null ? 'Global Portfolio' : formatBotLabel(selectedBot)} icon={Layers3} />
            </div>
          </motion.section>
        )}

        {tab === 'trades' && (
          <motion.section
            key="trades"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.16 }}
            className="relative z-10 px-4 mt-3 space-y-2.5"
          >
            {topTrades.length === 0 && (
              <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-elevated)] p-4 text-[11px] text-[var(--text-muted)]">No trades yet.</div>
            )}

            {topTrades.map((trade, idx) => (
              <article key={`${trade.symbol}-${trade.entrytime}-${idx}`} className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-elevated)]/92 p-3.5 shadow-[0_10px_18px_rgba(0,0,0,0.12)]">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-black truncate">{trade.symbol}</p>
                    <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-data">
                      {new Date(trade.entrytime).toLocaleString('es-ES', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>

                  <span className={clsx('text-[10px] uppercase font-black px-2 py-1 rounded-md border', trade.direction === 'Buy' ? 'bg-blue-500/15 text-blue-300 border-blue-400/25' : 'bg-orange-500/15 text-orange-300 border-orange-400/25')}>
                    {trade.direction}
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-2">
                  <div className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-surface)]/65 px-2 py-1.5">
                    <p className="text-[9px] uppercase tracking-wider font-bold text-[var(--text-muted)]">PnL</p>
                    <p className={clsx('font-data text-[12px] font-black', trade.netpnl >= 0 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
                      {formatCurrency(trade.netpnl)}
                    </p>
                  </div>

                  <div className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-surface)]/65 px-2 py-1.5">
                    <p className="text-[9px] uppercase tracking-wider font-bold text-[var(--text-muted)]">R</p>
                    <p className="font-data text-[12px] font-black text-[var(--text-secondary)]">{toNumber(trade.r_multiple).toFixed(2)}</p>
                  </div>

                  <div className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-surface)]/65 px-2 py-1.5">
                    <p className="text-[9px] uppercase tracking-wider font-bold text-[var(--text-muted)]">Bot</p>
                    <p className="font-data text-[12px] font-black text-[var(--text-secondary)]">{trade.bot_id ?? '-'}</p>
                  </div>
                </div>
              </article>
            ))}
          </motion.section>
        )}

        {tab === 'live' && (
          <motion.section
            key="live"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.16 }}
            className="relative z-10 px-4 mt-3 space-y-2.5"
          >
            {liveData.length === 0 && (
              <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-elevated)] p-4 text-[11px] text-[var(--text-muted)]">No live positions.</div>
            )}

            {liveData.map((pos: LivePosition, idx: number) => {
              const profit = toNumber(pos.profit)
              return (
                <article key={`${pos.ticket  idx}`} className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-elevated)]/92 p-3.5 shadow-[0_10px_18px_rgba(0,0,0,0.12)]">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-black truncate">{pos.symbol  'N/A'}</p>
                      <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Ticket #{pos.ticket  '-'}</p>
                    </div>
                    <div className="inline-flex items-center gap-1 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2 py-1">
                      <Building2 className="w-3 h-3 text-[var(--c-info)]" />
                      <span className="text-[10px] uppercase tracking-wider font-bold text-[var(--text-secondary)]">Live</span>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2 text-[10px]">
                    <div className="rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)]/70 px-2 py-1.5">
                      <p className="text-[var(--text-muted)] uppercase tracking-wider">Type</p>
                      <p className="font-bold text-[var(--text-secondary)]">{pos.type ?? '-'}</p>
                    </div>
                    <div className="rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)]/70 px-2 py-1.5">
                      <p className="text-[var(--text-muted)] uppercase tracking-wider">Lots</p>
                      <p className="font-data text-[var(--text-secondary)]">{toNumber(pos.volume).toFixed(2)}</p>
                    </div>
                    <div className="rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)]/70 px-2 py-1.5">
                      <p className="text-[var(--text-muted)] uppercase tracking-wider">PnL</p>
                      <p className={clsx('font-data font-bold', profit >= 0 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
                        {formatCurrency(profit)}
                      </p>
                    </div>
                  </div>
                </article>
              )
            })}
          </motion.section>
        )}
      </AnimatePresence>

      <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-[var(--bg-border)] bg-[var(--bg-elevated)]/95 px-2.5 py-2.5 backdrop-blur-xl">
        <div className="mx-auto grid max-w-md grid-cols-3 gap-2 rounded-xl border border-[var(--bg-border)] bg-[var(--bg-base)]/80 p-1.5">
          {TAB_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = tab === item.key
            return (
              <button
                key={item.key}
                onClick={() => setTab(item.key as 'overview'  'trades'  'live')}
                className={clsx(
                  'rounded-lg py-2 text-[10px] font-black uppercase tracking-[0.12em] flex items-center justify-center gap-1.5 transition-all',
                  isActive
                    ? 'bg-[var(--c-info)]/20 text-[var(--c-info)] border border-[var(--c-info)]/35'
                    : 'text-[var(--text-muted)] bg-[var(--bg-base)] border border-transparent',
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {item.label}
              </button>
            )
          })}
        </div>
      </nav>

      <div className="h-16" />
    </main>
  )
}
