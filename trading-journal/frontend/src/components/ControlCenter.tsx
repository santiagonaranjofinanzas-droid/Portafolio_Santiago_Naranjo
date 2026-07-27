'use client'

import { useMemo, useState, useEffect } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  ShieldAlert,
  Brain,
  ListTodo,
  Database,
  TrendingUp
} from 'lucide-react'
import { clsx } from 'clsx'
import ReactECharts from 'echarts-for-react'
import BloombergSentinel from './BloombergSentinel'

// ==========================================
// 1. Types
// ==========================================
type TradeRowRaw = {
  position_id?: number  string  null
  symbol?: string  null
  entrytime?: string  null
  exittime?: string  null
  direction?: string  null
  netpnl?: number  string  null
  r_multiple?: number  string  null
  volume?: number  string  null
  magic_number?: number  string  null
  bot_id?: number  string  null
  exit_reason?: number  string  null
  commission?: number  string  null
  gross_pnl?: number  string  null
}

type StatsPayload = {
  insights?: {
    type: 'success'  'warning'  'danger'  'info'
    metric: string
    text: string
    actionable: string
  }[]
  summary?: {
    net_profit?: number
    expectancy?: number
    sqn?: number
    sharpe?: number
    start_cap?: number
    end_equity?: number
  }
  perf?: {
    max_drawdown?: number
    pf?: number
    win_rate?: number
    payoff?: number
  }
  risk?: {
    var?: number
    cvar?: number
    garch_var?: number
    daily_vol?: number
    downside_vol?: number
    vol_regime?: string
  }
  quant?: {
    mc_dd_p10?: number
    prob_ruin_10pct?: number
    hmm_regime?: string
  }
  history?: TradeRowRaw[]
  equity_curve?: {
    date: string
    Fecha?: string
    balance?: number
    equity: number
    drawdown: number
  }[]
  account_snapshot?: {
    balance: number
    equity: number
    currency: string
    captured_at: string
    account_type?: 'Real'  'Demo'
    account_login?: string
  }
}

export type ControlCenterView = 'home'  'integrity'  'risk'  'execution'

type ControlCenterProps = {
  stats: StatsPayload  undefined
  selectedBot: number  null
  view?: ControlCenterView
}

// ==========================================
// 2. Helpers
// ==========================================
function toNumber(value: unknown, fallback = 0): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function formatCurrency(val: number) {
  const safeVal = Number.isFinite(val) ? val : 0
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(safeVal)
}

function asMs(iso: string): number {
  const ms = Date.parse(iso)
  return Number.isFinite(ms) ? ms : 0
}

function formatTime(value: unknown): string {
  if (!value) return 'N/A'
  const date = new Date(String(value))
  return Number.isFinite(date.getTime()) ? date.toLocaleTimeString() : 'N/A'
}

// ==========================================
// 3. Main Component
// ==========================================
export default function ControlCenter({ stats }: ControlCenterProps) {
  // Extract data
  const historyRaw = stats?.history
  const trades = useMemo(() => (Array.isArray(historyRaw) ? historyRaw : []).map((raw) => ({
    positionId: Math.trunc(toNumber(raw.position_id)),
    symbol: String(raw.symbol ?? 'N/A'),
    entrytime: String(raw.entrytime ?? ''),
    exittime: String(raw.exittime ?? ''),
    direction: String(raw.direction ?? 'N/A'),
    netPnl: toNumber(raw.netpnl, 0),
    rMultiple: toNumber(raw.r_multiple, 0),
    volume: toNumber(raw.volume, 0),
  })), [historyRaw])

  const totalNet = toNumber(stats?.summary?.net_profit, trades.reduce((acc, t) => acc + t.netPnl, 0))
  const maxDrawdown = Math.abs(toNumber(stats?.perf?.max_drawdown, 0))
  const pf = toNumber(stats?.perf?.pf, 0)
  const winRate = toNumber(stats?.perf?.win_rate, trades.filter(t => t.netPnl > 0).length / Math.max(1, trades.length))
  
  const riskVaR = toNumber(stats?.risk?.var, 0)
  const sqn = toNumber(stats?.summary?.sqn, 0)

  // Status computation
  const [nowMs, setNowMs] = useState<number>(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 60000)
    return () => clearInterval(id)
  }, [])

  const lastTradeMs = useMemo(() => {
    if (trades.length === 0) return 0
    return trades.reduce((latest, t) => {
      const ms = asMs(t.exittime  t.entrytime)
      return ms > latest ? ms : latest
    }, 0)
  }, [trades])

  const hoursSinceLastTrade = lastTradeMs > 0 ? Math.max(0, (nowMs - lastTradeMs) / (60 * 60 * 1000)) : 999
  const systemStatus = hoursSinceLastTrade < 24 ? 'ACTIVE' : 'IDLE'

  // Equity & Balance
  const startCap = toNumber(stats?.summary?.start_cap, 5000)
  const summaryEquity = toNumber(stats?.summary?.end_equity, startCap + totalNet)
  const snapshotBalance = toNumber(stats?.account_snapshot?.balance, Number.NaN)
  const currentBalance = Number.isFinite(snapshotBalance) ? snapshotBalance : summaryEquity
  const isPositive = totalNet >= 0

  // Chart Data
  const chartOptions = useMemo(() => {
    const curve = stats?.equity_curve  []
    if (curve.length === 0) return {}

    const dates = curve.map(d => {
      const ms = Date.parse(d.date  d.Fecha  '')
      return Number.isNaN(ms) ? 'N/A' : new Date(ms).toLocaleDateString()
    })
    const equityData = curve.map(d => d.equity)
    const drawdownData = curve.map(d => d.drawdown * 100) // Convert to %

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#111827',
        borderColor: '#1F2937',
        textStyle: { color: '#E5E7EB' }
      },
      grid: {
        top: 20,
        right: 40,
        bottom: 20,
        left: 60,
        containLabel: false
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: 'rgba(128, 128, 128, 0.2)' } },
        axisLabel: { color: '#888888' }
      },
      yAxis: [
        {
          type: 'value',
          scale: true,
          splitLine: { lineStyle: { color: 'rgba(128, 128, 128, 0.1)', type: 'dashed' } },
          axisLabel: { color: '#888888' }
        },
        {
          type: 'value',
          position: 'right',
          inverse: true, // Drawdown goes down
          splitLine: { show: false },
          axisLabel: { show: false },
          max: 100, // Max DD %
          min: 0
        }
      ],
      series: [
        {
          name: 'Equity',
          type: 'line',
          data: equityData,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#3B82F6', width: 2 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(59, 130, 246, 0.2)' },
                { offset: 1, color: 'rgba(59, 130, 246, 0)' }
              ]
            }
          }
        },
        {
          name: 'Drawdown (%)',
          type: 'line',
          yAxisIndex: 1,
          data: drawdownData,
          smooth: true,
          symbol: 'none',
          lineStyle: { opacity: 0 },
          areaStyle: {
            color: 'rgba(239, 68, 68, 0.15)'
          }
        }
      ]
    }
  }, [stats?.equity_curve])

  // Smart Insights (from Backend)
  const insights = stats?.insights  [
    {
      type: 'info',
      metric: 'baseline',
      text: 'Calculando baseline de métricas...',
      actionable: 'Recopilando datos suficientes para análisis de Edge.'
    }
  ]

  // Trade Table filters
  const [tradeFilter, setTradeFilter] = useState<'ALL''WINNERS''LOSERS'>('ALL')
  const filteredTrades = useMemo(() => {
    let t = [...trades].sort((a,b) => asMs(b.exittime) - asMs(a.exittime))
    if (tradeFilter === 'WINNERS') t = t.filter(x => x.netPnl > 0)
    if (tradeFilter === 'LOSERS') t = t.filter(x => x.netPnl < 0)
    return t.slice(0, 15)
  }, [trades, tradeFilter])

  const riskScore = clamp((maxDrawdown * 100) / 15, 0, 1) // 0 to 1

  return (
    <div className="space-y-6 max-w-[1440px] mx-auto text-[var(--text-primary)]">
      
      {/* 1. HEADER */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 py-4 px-6 rounded-2xl bg-[var(--bg-void)] border border-[var(--bg-border)]">
        <div>
          <p className="text-sm font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1">Total Equity</p>
          <div className="flex items-baseline gap-4">
            <h1 className="text-4xl md:text-5xl font-black font-data tracking-tight text-[var(--text-primary)]">
              {formatCurrency(currentBalance)}
            </h1>
            <div className={clsx("flex items-center gap-1 font-bold text-sm", isPositive ? "text-[var(--c-positive)]" : "text-[var(--c-negative)]")}>
              {isPositive ? <ArrowUpRight className="w-4 h-4"/> : <ArrowDownRight className="w-4 h-4"/>}
              <span>{formatCurrency(totalNet)} PnL</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {stats?.account_snapshot && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--bg-surface)] border border-[var(--bg-border-strong)]">
              <span className={clsx(
                "px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider border",
                stats.account_snapshot.account_type === 'Real'
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" 
                  : "bg-blue-500/10 text-blue-400 border-blue-500/20"
              )}>
                {stats.account_snapshot.account_type  'Account'}
              </span>
              <span className="text-xs font-bold text-[var(--text-primary)]">
                {stats.account_snapshot.account_login  'MT5'}
              </span>
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--bg-surface)] border border-[var(--bg-border-strong)]">
            <span className={clsx("w-2 h-2 rounded-full", systemStatus === 'ACTIVE' ? "bg-[var(--c-positive)] animate-pulse" : "bg-[var(--c-warning)]")} />
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
              System {systemStatus}
            </span>
          </div>
          {stats?.account_snapshot && (
            <div className="text-[10px] text-[var(--text-muted)] text-right">
              <p>Last Sync</p>
              <p>{formatTime(stats.account_snapshot.captured_at)}</p>
            </div>
          )}
        </div>
      </header>

      {/* 2. PERFORMANCE ROW */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Net Profit', val: formatCurrency(totalNet), color: isPositive ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]' },
          { label: 'Win Rate', val: `${(winRate * 100).toFixed(1)}%`, color: 'text-[var(--text-primary)]' },
          { label: 'Profit Factor', val: pf.toFixed(2), color: pf >= 1.5 ? 'text-[var(--c-positive)]' : pf >= 1 ? 'text-[var(--c-warning)]' : 'text-[var(--c-negative)]' },
          { label: 'Max Drawdown', val: `${(maxDrawdown * 100).toFixed(2)}%`, color: maxDrawdown > 0.08 ? 'text-[var(--c-negative)]' : 'text-[var(--text-primary)]' },
        ].map((kpi, i) => (
          <div key={i} className="widget p-5 hover:bg-[var(--bg-hover)] transition-colors">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)] mb-2">{kpi.label}</p>
            <p className={clsx('font-data text-2xl font-black', kpi.color)}>{kpi.val}</p>
          </div>
        ))}
      </section>

      {/* 3. MAIN AREA */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        
        {/* LEFT COLUMN: 8/12 */}
        <div className="xl:col-span-8 flex flex-col gap-4">
          
          {/* ACTION PANEL (DECISION ENGINE) */}
          <div className="glass-card-heavy px-6 py-5 border-[var(--bg-border-strong)] flex flex-col gap-4 relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/5 via-blue-500/5 to-transparent pointer-events-none" />
            <div className="flex items-center gap-2 mb-1 relative z-10">
              <span className="h-2 w-2 rounded-full bg-[var(--c-neutral)] animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
              <Brain className="w-5 h-5 text-[var(--c-neutral)]" />
              <h2 className="text-xs font-black uppercase tracking-[0.15em] text-[var(--text-secondary)]">Prioridades de Hoy</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative z-10">
              {insights.map((insight, idx) => (
                <div key={idx} 
                  className={clsx(
                    "p-4 rounded-xl border transition-all hover:scale-[1.01]",
                    insight.type === 'danger' ? "bg-[var(--c-negative-dim)] hover:border-[var(--c-negative)]" :
                    insight.type === 'warning' ? "bg-[var(--c-warning-dim)] hover:border-[var(--c-warning)]" :
                    insight.type === 'success' ? "bg-[var(--c-positive-dim)] hover:border-[var(--c-positive)]" :
                    "bg-[var(--c-neutral-dim)] hover:border-[var(--c-neutral)]"
                  )}
                  style={{
                    borderColor: insight.type === 'danger' ? 'rgba(244, 63, 94, 0.2)' :
                                 insight.type === 'warning' ? 'rgba(234, 179, 8, 0.2)' :
                                 insight.type === 'success' ? 'rgba(16, 185, 129, 0.2)' :
                                 'rgba(59, 130, 246, 0.2)'
                  }}
                >
                  <div className="text-[10px] font-black uppercase tracking-widest mb-2 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span>
                        {insight.type === 'danger' && ' '}
                        {insight.type === 'warning' && ' '}
                      </span>
                      <span className="text-[var(--text-secondary)] font-bold">{insight.metric}</span>
                    </div>
                    {insight.type === 'danger'  insight.type === 'warning' ? (
                      <AlertTriangle className={clsx("w-3.5 h-3.5", insight.type === 'danger' ? "text-[var(--c-negative)]" : "text-[var(--c-warning)]")} />
                    ) : (
                      <Activity className={clsx("w-3.5 h-3.5", insight.type === 'success' ? "text-[var(--c-positive)]" : "text-[var(--c-neutral)]")} />
                    )}
                  </div>
                  <p className="text-sm font-semibold text-[var(--text-primary)] leading-relaxed">{insight.text}</p>
                  <p className={clsx(
                    "text-xs font-bold mt-2",
                    insight.type === 'danger' ? "text-[var(--c-negative)]" :
                    insight.type === 'warning' ? "text-[var(--c-warning)]" :
                    insight.type === 'success' ? "text-[var(--c-positive)]" :
                    "text-[var(--c-neutral)]"
                  )}>
                    → {insight.actionable}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* OPERATIONAL BLOCKS (3 Cards) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* INTEGRIDAD */}
            <div className="widget p-5 flex flex-col gap-3">
              <div className="flex items-center gap-2 text-[var(--text-muted)]">
                <Database className="w-4 h-4" />
                <span className="text-[10px] font-bold uppercase tracking-widest">Integridad</span>
              </div>
              <div className="flex-1">
                <p className="text-2xl font-data font-bold text-[var(--text-primary)]">{systemStatus}</p>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">Sync: {hoursSinceLastTrade.toFixed(1)}h ago</p>
              </div>
              <div className="pt-3 border-t border-[var(--bg-border)] flex justify-between items-center">
                <span className="text-[10px] text-[var(--text-muted)]">Reliability</span>
                <span className="text-[10px] font-bold text-[var(--c-positive)]">99.8%</span>
              </div>
            </div>

            {/* RIESGO */}
            <div className="widget p-5 flex flex-col gap-3">
              <div className="flex items-center gap-2 text-[var(--text-muted)]">
                <ShieldAlert className="w-4 h-4" />
                <span className="text-[10px] font-bold uppercase tracking-widest">Riesgo</span>
              </div>
              <div className="flex-1">
                <p className="text-2xl font-data font-bold text-[var(--text-primary)]">{(riskVaR*100).toFixed(1)}%</p>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">GARCH-VaR (Daily)</p>
              </div>
              <div className="pt-3 border-t border-[var(--bg-border)] flex justify-between items-center">
                <span className="text-[10px] text-[var(--text-muted)]">Status</span>
                <span className={clsx("text-[10px] font-bold", riskVaR < 0.02 ? "text-[var(--c-positive)]" : "text-[var(--c-warning)]")}>
                  {riskVaR < 0.02 ? 'Safe' : 'Watch'}
                </span>
              </div>
            </div>

            {/* EJECUCION */}
            <div className="widget p-5 flex flex-col gap-3">
              <div className="flex items-center gap-2 text-[var(--text-muted)]">
                <Activity className="w-4 h-4" />
                <span className="text-[10px] font-bold uppercase tracking-widest">Ejecución</span>
              </div>
              <div className="flex-1">
                <p className="text-2xl font-data font-bold text-[var(--text-primary)]">{sqn.toFixed(2)}</p>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">System Quality (SQN)</p>
              </div>
              <div className="pt-3 border-t border-[var(--bg-border)] flex justify-between items-center">
                <span className="text-[10px] text-[var(--text-muted)]">Quality</span>
                <span className={clsx("text-[10px] font-bold", sqn > 2 ? "text-[var(--c-positive)]" : "text-[var(--c-neutral)]")}>
                  {sqn > 2 ? 'Superb' : 'Normal'}
                </span>
              </div>
            </div>
          </div>

          {/* EQUITY CHART */}
          <div className="widget p-5 h-[350px] flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-muted)]">Equity Performance</h2>
            </div>
            <div className="flex-1 w-full min-h-0 relative">
              {stats?.equity_curve && stats.equity_curve.length > 0 ? (
                <ReactECharts 
                  option={chartOptions} 
                  style={{ height: '100%', width: '100%' }}
                  opts={{ renderer: 'svg' }}
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-[var(--text-muted)] text-sm">
                  Insufficient history for chart
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: 4/12 */}
        <div className="xl:col-span-4 flex flex-col gap-6">
          
          {/* BLOOMBERG / INSTITUTIONAL SENTINEL */}
          <BloombergSentinel colsClass="grid-cols-1 md:grid-cols-2 xl:grid-cols-1" minimal={true} />

          {/* RISK PULSE (Surgical) */}
          <div className="widget p-5">
            <div className="flex items-center gap-2 mb-4">
              <ShieldAlert className="w-4 h-4 text-[var(--c-negative)]" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]">Risk Pulse</h2>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-[10px] uppercase text-[var(--text-muted)]">VaR 99%</p>
                  <p className="font-data text-lg font-bold text-[var(--text-primary)] mt-1">{(riskVaR*100).toFixed(2)}%</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-[var(--text-muted)]">GARCH Forecast</p>
                  <p className="font-data text-lg font-bold text-[var(--c-neutral)] mt-1">{(stats?.risk?.garch_var ? stats.risk.garch_var * 100 : 0).toFixed(2)}%</p>
                </div>
              </div>
              <div className="pt-4 border-t border-[var(--bg-border)]">
                <div className="flex justify-between mb-1">
                  <p className="text-[10px] uppercase text-[var(--text-muted)]">Drawdown Stress</p>
                  <p className="font-data text-xs font-bold text-[var(--text-primary)]">{(maxDrawdown*100).toFixed(1)}%</p>
                </div>
                <div className="h-1.5 w-full bg-[var(--bg-surface)] rounded-full overflow-hidden flex">
                  <div className="h-full bg-[var(--c-positive)] transition-all" style={{ width: `${clamp((1 - riskScore)*100, 0, 100)}%` }} />
                  <div className="h-full bg-[var(--c-negative)] transition-all" style={{ width: `${clamp(riskScore*100, 0, 100)}%` }} />
                </div>
              </div>
            </div>
          </div>

          {/* SYSTEM STATS */}
          <div className="widget p-5">
             <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-4 h-4 text-[var(--c-positive)]" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]">Performance stats</h2>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between items-center py-2 border-b border-[var(--bg-border)]">
                <span className="text-xs text-[var(--text-muted)]">Sharpe Ratio</span>
                <span className="text-xs font-data font-bold text-[var(--text-primary)]">{(stats?.summary?.sharpe ?? 0).toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-[var(--bg-border)]">
                <span className="text-xs text-[var(--text-muted)]">Profit Factor</span>
                <span className="text-xs font-data font-bold text-[var(--text-primary)]">{(stats?.perf?.pf ?? 0).toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-xs text-[var(--text-muted)]">Expectancy</span>
                <span className="text-xs font-data font-bold text-[var(--text-primary)]">{(stats?.summary?.expectancy ?? 0).toFixed(2)}R</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4. TRADE LOG */}
      <section className="widget overflow-hidden flex flex-col">
        <div className="px-5 py-4 border-b border-[var(--bg-border)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ListTodo className="w-4 h-4 text-[var(--text-muted)]" />
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]">Trade Log</h2>
          </div>
          <div className="flex gap-2">
            {(['ALL', 'WINNERS', 'LOSERS'] as const).map(f => (
              <button 
                key={f}
                onClick={() => setTradeFilter(f)}
                className={clsx(
                  "px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider transition-colors",
                  tradeFilter === f 
                    ? "bg-[var(--c-neutral-dim)] text-[var(--c-neutral)] border border-[rgba(59,130,246,0.2)]" 
                    : "bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                )}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--bg-void)] text-[var(--text-muted)] text-[10px] uppercase tracking-widest">
              <tr>
                <th className="px-5 py-3 font-medium">Date</th>
                <th className="px-5 py-3 font-medium">Symbol</th>
                <th className="px-5 py-3 font-medium">Dir</th>
                <th className="px-5 py-3 font-medium text-right">Vol</th>
                <th className="px-5 py-3 font-medium text-right">R-Mult</th>
                <th className="px-5 py-3 font-medium text-right">PnL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--bg-border)]">
              {filteredTrades.map((t, i) => (
                <tr key={`${t.positionId}-${i}`} className="hover:bg-[var(--bg-hover)] transition-colors group">
                  <td className="px-5 py-3 font-data text-[var(--text-muted)]">{t.exittime.split('T')[0]  t.entrytime.split('T')[0]}</td>
                  <td className="px-5 py-3 font-bold text-[var(--text-primary)]">{t.symbol}</td>
                  <td className="px-5 py-3">
                    <span className={clsx(
                      "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                      t.direction.toUpperCase() === 'BUY' ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"
                    )}>
                      {t.direction}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-data text-right text-[var(--text-muted)]">{t.volume.toFixed(2)}</td>
                  <td className="px-5 py-3 font-data text-right text-[var(--text-primary)]">{t.rMultiple.toFixed(2)}R</td>
                  <td className={clsx(
                    "px-5 py-3 font-data font-bold text-right",
                    t.netPnl >= 0 ? "text-[var(--c-positive)]" : "text-[var(--c-negative)]"
                  )}>
                    {formatCurrency(t.netPnl)}
                  </td>
                </tr>
              ))}
              {filteredTrades.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-[var(--text-muted)]">
                    No trades match the current filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  )
}

function clamp(val: number, min: number, max: number) {
  return Math.max(min, Math.min(max, val))
}
