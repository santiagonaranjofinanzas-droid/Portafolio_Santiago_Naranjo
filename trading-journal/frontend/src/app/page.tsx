'use client'

import { useMetrics, useAccounts } from '@/hooks/useMetrics'
import TradeHistory from '@/components/TradeHistory'
import EquityChart from '@/components/EquityChart'
import TradeDetailDrawer, { type TradeDetail } from '@/components/TradeDetailDrawer'
import RiskAnalytics from '@/components/RiskAnalytics'
import DataJournal from '@/components/DataJournal'
import AIAnalystPanel from '@/components/AIAnalystPanel'
import TemporalDynamics from '@/components/TradeCalendar'
import MT5StatusIndicator from '@/components/MT5StatusIndicator'
import ControlCenter from '@/components/ControlCenter'
import MacroNewsPanel from '@/components/MacroNewsPanel'
import TradingJournal from '@/components/TradingJournal'
import QuantSimulator from '@/components/QuantSimulator'
import Link from 'next/link'
import {
  ShieldAlert, LayoutDashboard, Database, LineChart, Brain, Settings,
  RefreshCw, Sun, Moon, Crown, Cpu, Newspaper, BookOpen, BarChart2,
  TrendingUp, ChevronLeft, ChevronRight, Menu,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { useState, useEffect, useMemo } from 'react'
import { clsx } from 'clsx'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { buildApiUrl } from '@/lib/api'
import type { AiSeed } from '@/lib/ai'

function SkeletonLoader() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4" style={{background:'var(--bg-base)'}}>
      <RefreshCw className="w-5 h-5 text-[var(--c-neutral)] animate-spin" />
      <p className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-widest">Initializing Terminal</p>
      <div className="w-48 h-1 rounded-full overflow-hidden" style={{background:'var(--bg-border)'}}>
        <div className="h-full rounded-full animate-pulse" style={{width:'60%',background:'var(--c-neutral)',opacity:0.3}} />
      </div>
    </div>
  )
}

type AppTheme = 'dark'  'light'  'gold'
type NavItem = { name: string; icon: typeof LayoutDashboard; section: string }
type AccountOption = { account_login: string; server_name: string; account_type: 'Real'  'Demo' }

const navItems: NavItem[] = [
  { name: 'Resumen',           icon: LayoutDashboard, section: 'CORE' },
  { name: 'Centro de Control',  icon: Cpu,             section: 'CORE' },
  { name: 'Macro Intel',        icon: Newspaper,       section: 'ANALISIS' },
  { name: 'Trading Journal',    icon: BookOpen,        section: 'ANALISIS' },
  { name: 'Data Journal',       icon: Database,        section: 'ANALISIS' },
  { name: 'Risk Analytics',     icon: ShieldAlert,     section: 'ANALISIS' },
  { name: 'Temporal Dynamics',  icon: BarChart2,       section: 'ANALISIS' },
  { name: 'Analista IA',        icon: Brain,           section: 'IA' },
  { name: 'Ajustes',            icon: Settings,        section: 'CONFIG' },
]
const sections = ['CORE', 'ANALISIS', 'IA', 'CONFIG']
const tabSubtitle: Record<string, string> = {
  Resumen: 'Resumen de portafolio y estado en tiempo real',
  'Centro de Control': 'Guía para clientes minoristas premium',
  'Macro Intel': 'Noticias de alto impacto con interpretación cuantitativa',
  'Trading Journal': 'Registro emocional y técnico de operaciones',
  'Data Journal': 'Análisis detallado de trades',
  'Temporal Dynamics': 'Comportamiento temporal del sistema',
  'Risk Analytics': 'Analítica cuantitativa avanzada',
  'Analista IA': 'Copiloto IA para diagnósticos y reportes',
  Ajustes: 'Preferencias de la terminal',
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('Resumen')
  const [selectedTrade, setSelectedTrade] = useState<TradeDetail  null>(null)
  const [selectedBot, setSelectedBot] = useState<number  null>(null)
  const [selectedAccountKey, setSelectedAccountKey] = useState<string>('auto')
  const [nowMs, setNowMs] = useState(() => Date.now())
  const [aiSeed, setAiSeed] = useState<AiSeed  null>(null)
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem('bk-sidebar-collapsed') === 'true'
  })
  const [theme, setTheme] = useState<AppTheme>(() => {
    if (typeof window === 'undefined') return 'dark'
    const s = localStorage.getItem('bk-terminal-theme')
    return s === 'light'  s === 'gold' ? s : 'dark'
  })

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); localStorage.setItem('bk-terminal-theme', theme) }, [theme])
  useEffect(() => { localStorage.setItem('bk-sidebar-collapsed', String(collapsed)) }, [collapsed])
  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 60000)
    return () => window.clearInterval(timer)
  }, [])

  const [selectedAccountLogin, selectedAccountServer] = useMemo(() => {
    if (selectedAccountKey === 'auto') return [null, null]
    const [login, server] = selectedAccountKey.split(':')
    return [login, server]
  }, [selectedAccountKey])

  const queryClient = useQueryClient()
  const { data: accounts = [] } = useAccounts()
  const { data: stats, isLoading, error } = useMetrics(365, selectedBot, selectedAccountLogin, selectedAccountServer)
  const lowSignificance = stats?.quant?.significance !== 'High'
  const summaryNav = Number((stats?.summary?.start_cap ?? 0) + (stats?.summary?.net_profit ?? 0))
  const globalNav = Number(stats?.account_snapshot?.balance ?? summaryNav)
  const navValue = selectedBot === null ? globalNav : summaryNav
  const formatBotLabel = (bot: number) => (bot === 0 ? 'Manual (0)' : `Node ${bot}`)

  const history = stats?.history ?? []
  const equityCurve = useMemo(() => stats?.equity_curve ?? [], [stats?.equity_curve])
  const journalAccountLogin = selectedAccountLogin ?? stats?.account_snapshot?.account_login ?? null
  const journalServerName = selectedAccountServer ?? stats?.account_snapshot?.server_name ?? null
  const tradeCount = history.length
  const riskReturnSeries = useMemo(() => {
    const explicitReturns = equityCurve
      .map((point: { return?: number  string  null }) => Number(point?.return))
      .filter((value: number) => Number.isFinite(value))

    if (explicitReturns.length >= 6) return explicitReturns

    return equityCurve
      .map((point: { pnl?: number  string  null; equity?: number  string  null }) => {
        const pnl = Number(point?.pnl)
        const equity = Number(point?.equity)
        const startingEquity = equity - pnl
        if (!Number.isFinite(pnl)  !Number.isFinite(startingEquity)  startingEquity <= 0) return null
        return pnl / startingEquity
      })
      .filter((value: number  null): value is number => value !== null && Number.isFinite(value))
  }, [equityCurve])
  const winRatePct = (stats?.perf?.win_rate ?? 0) * 100
  const pfValue = stats?.perf?.pf ?? 0
  const roiPct = (stats?.summary?.total_return ?? 0) * 100
  const netProfit = stats?.summary?.net_profit ?? 0
  const expectancyR = stats?.summary?.expectancy ?? 0
  const expectancyCash = stats?.summary?.expectancy_cash ?? 0
  const maxDrawdownPct = (stats?.perf?.max_drawdown ?? 0) * 100
  const maxDrawdownCash = stats?.perf?.max_drawdown_cash ?? 0
  const cagrPct = (stats?.perf?.cagr ?? 0) * 100
  const avgWin = stats?.perf?.avg_win ?? 0
  const avgLoss = stats?.perf?.avg_loss ?? 0
  const avgDuration = stats?.perf?.avg_duration_min ?? 0
  const var95Pct = (stats?.risk?.var ?? 0) * 100
  const cvarPct = (stats?.risk?.cvar ?? 0) * 100
  const dailyVolPct = (stats?.risk?.daily_vol ?? 0) * 100
  const downsideVolPct = (stats?.risk?.downside_vol ?? 0) * 100
  const endEquity = stats?.summary?.end_equity ?? navValue
  const balance = stats?.account_snapshot?.balance ?? endEquity
  const equity = stats?.account_snapshot?.equity ?? endEquity

  const parseTime = (v: unknown) => {
    if (!v  v === 'Invalid Date') return null
    if (!(typeof v === 'string'  typeof v === 'number'  v instanceof Date)) return null
    let d = new Date(v)
    if (typeof v === 'number' && v < 1e12) d = new Date(v * 1000)
    return isNaN(d.getTime()) ? null : d
  }
  const lastTrade = tradeCount > 0 ? history[tradeCount - 1] : null
  const lastTradeDate = parseTime(lastTrade?.exittime ?? lastTrade?.entrytime)
  const firstTradeDate = tradeCount > 0 ? parseTime(history[0]?.entrytime) : null
  const dataSpanDays = lastTradeDate && firstTradeDate ? Math.max(1, Math.round((lastTradeDate.getTime() - firstTradeDate.getTime()) / 86400000)) : 0
  const lastTradeAgeMin = lastTradeDate ? Math.max(0, Math.floor((nowMs - lastTradeDate.getTime()) / 60000)) : null
  const freshnessLabel = lastTradeAgeMin === null ? 'Sin Datos' : lastTradeAgeMin <= 20 ? 'En Tiempo Real' : lastTradeAgeMin <= 240 ? 'Inactivo' : 'Desconectado'
  const freshnessTone = lastTradeAgeMin !== null && lastTradeAgeMin <= 240 ? 'ok' : 'warn'

  const syncMutation = useMutation({
    mutationFn: async () => { const r = await fetch(buildApiUrl('/sync'), { method: 'POST' }); if (!r.ok) throw new Error('Sync Failed'); return r.json() },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['metrics'] }) }
  })

  const openAiAnalyst = (focus: string, prompt: string) => { setAiSeed({ id: Date.now(), focus, prompt }); setActiveTab('Analista IA') }

  const cycleTheme = () => { const order: AppTheme[] = ['dark','light','gold']; setTheme(order[(order.indexOf(theme)+1)%3]) }
  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : Crown

  if (error) return (
    <div className="flex items-center justify-center min-h-screen" style={{background:'var(--bg-base)'}}>
      <div className="widget p-8 text-center max-w-sm">
        <ShieldAlert className="w-8 h-8 mx-auto mb-3" style={{color:'var(--c-negative)'}} />
        <h2 className="text-sm font-bold" style={{color:'var(--c-negative)'}}>Connection Failed</h2>
        <p className="text-xs mt-1" style={{color:'var(--text-muted)'}}>Backend unreachable. Check API base URL.</p>
      </div>
    </div>
  )
  if (isLoading) return <SkeletonLoader />

  return (
    <div className="app-shell">
      {/* ═══ SIDEBAR ═══ */}
      <aside className={clsx('sidebar hidden md:flex', collapsed && 'collapsed')}>
        <button className="collapse-btn" onClick={() => setCollapsed(!collapsed)} title={collapsed ? 'Expand' : 'Collapse'}>
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
        </button>
        <div className="sidebar-logo">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{background:'var(--c-neutral-dim)'}}>
            <LineChart className="w-4 h-4" style={{color:'var(--c-neutral)'}} />
          </div>
          <div>
            <h1>BLACK KNIGHT</h1>
            <p className="logo-sub text-[8px] uppercase tracking-[0.2em] font-bold" style={{color:'var(--text-ghost)'}}>Quant Terminal</p>
          </div>
        </div>
        <nav className="sidebar-nav">
          {sections.map(s => {
            const items = navItems.filter(i => i.section === s)
            if (!items.length) return null
            return (
              <div key={s} className="mb-2">
                <div className="nav-section-label">{s}</div>
                {items.map(item => {
                  const Icon = item.icon
                  return (
                    <button key={item.name} onClick={() => setActiveTab(item.name)}
                      className={clsx('nav-item', activeTab === item.name && 'active')}
                      title={collapsed ? item.name : undefined}>
                      <Icon className="nav-icon" />
                      <span className="nav-label">{item.name}</span>
                    </button>
                  )
                })}
              </div>
            )
          })}
        </nav>
        <div className="sidebar-footer">
          <Link href="/mobile" className="text-[10px] uppercase tracking-widest font-bold hover:opacity-80 transition-opacity" style={{color:'var(--c-neutral)'}}>
            Mobile View →
          </Link>
        </div>
      </aside>

      {/* ═══ MAIN ═══ */}
      <main className="main-content">
        {/* ── TOP BAR ── */}
        <div className="topbar">
          <div className="topbar-section">
            <button className="btn btn-icon md:hidden" onClick={() => setCollapsed(!collapsed)}><Menu className="w-4 h-4" /></button>
            <div>
              <div className="topbar-stat-label">NAV (Equity)</div>
              <div className="topbar-stat-value font-data">
                ${(equity).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}
              </div>
            </div>
            {stats?.account_snapshot && (
              <>
                <div className="topbar-divider hidden lg:block" />
                <div className="hidden lg:block">
                  <div className="topbar-stat-label">Active Account</div>
                  <div className="text-xs font-data font-semibold flex items-center gap-1.5" style={{color:'var(--text-secondary)'}}>
                    <span className={clsx(
                      "px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider border",
                      stats.account_snapshot.account_type === 'Real' 
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" 
                        : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                    )}>
                      {stats.account_snapshot.account_type}
                    </span>
                    <span>{stats.account_snapshot.account_login}</span>
                  </div>
                </div>
                <div className="hidden lg:block">
                  <MT5StatusIndicator 
                    compact 
                    accountLogin={selectedAccountLogin} 
                    serverName={selectedAccountServer} 
                  />
                </div>
              </>
            )}
          </div>
          <div className="topbar-section">
            {accounts.length > 0 && (
              <select 
                className="select-minimal font-data animate-fade-in" 
                value={selectedAccountKey} 
                onChange={e => setSelectedAccountKey(e.target.value)}
              >
                <option value="auto"> Auto-Switch</option>
                {(accounts as AccountOption[]).map((acc) => (
                  <option key={`${acc.account_login}:${acc.server_name}`} value={`${acc.account_login}:${acc.server_name}`}>
                    {acc.account_type === 'Real' ? '' : ''} {acc.account_type} · {acc.account_login}
                  </option>
                ))}
              </select>
            )}
            {stats?.available_bots?.length > 0 && (
              <select className="select-minimal font-data" value={selectedBot ?? ''} onChange={e => { const v = e.target.value; setSelectedBot(v === '' ? null : Number(v)) }}>
                <option value="">Global Portfolio</option>
                {stats.available_bots.map((b: number) => <option key={b} value={b}>{formatBotLabel(b)}</option>)}
              </select>
            )}
            <button className="btn btn-primary" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
              <RefreshCw className={clsx('w-3.5 h-3.5', syncMutation.isPending && 'animate-spin')} />
              {syncMutation.isPending ? 'Syncing' : 'Sync'}
            </button>
            <button className="btn btn-ghost btn-icon" onClick={cycleTheme} title="Theme">
              <ThemeIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── PAGE CONTENT ── */}
        <div className="page-content">
          <header className="page-header">
            <h2 className="page-title">{activeTab}</h2>
            <p className="page-subtitle">{tabSubtitle[activeTab] ?? 'Real-time quantitative surveillance'}</p>
          </header>

          {/* ═══ OVERVIEW ═══ */}
          {activeTab === 'Resumen' && (
            <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{duration:0.2}} className="space-y-4">
              {/* Freshness + Scope */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className={clsx('ops-badge', freshnessTone === 'ok' ? 'ops-badge--ok' : 'ops-badge--warn')}>{freshnessLabel}</span>
                  <span className="text-xs font-data" style={{color:'var(--text-muted)'}}>{tradeCount} trades · {dataSpanDays}d span</span>
                </div>
                <span className="text-xs font-data flex items-center gap-1.5" style={{color:'var(--text-muted)'}}>
                  {stats?.account_snapshot && (
                    <span className={clsx(
                      "px-1 py-0.5 rounded-[3px] text-[8px] font-black uppercase tracking-wider border",
                      stats.account_snapshot.account_type === 'Real' 
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" 
                        : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                    )}>
                      {stats.account_snapshot.account_type} ({stats.account_snapshot.account_login})
                    </span>
                  )}
                  <span>{selectedBot === null ? 'Global' : formatBotLabel(selectedBot)}</span>
                </span>
              </div>

              {/* MT5 Status */}
              <MT5StatusIndicator 
                statisticalAlert={lowSignificance ? `N=${history.length} · Baja significancia estadística` : null} 
                accountLogin={selectedAccountLogin}
                serverName={selectedAccountServer}
              />
              {stats?.methodology?.capital_verified === false && (
                <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-xs text-amber-300">
                  Capital histórico no verificable. Las métricas relativas a capital, VaR, drawdown, CAGR y Kelly se muestran como no disponibles hasta registrar un balance inicial válido.
                </div>
              )}

              {/* KPI Strip */}
              <div className="kpi-grid">
                <div className={clsx('kpi-card', netProfit >= 0 ? 'kpi-card--positive' : 'kpi-card--negative')}>
                  <div className="kpi-label">PnL Neto</div>
                  <div className={clsx('kpi-value font-data', netProfit >= 0 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
                    {netProfit >= 0 ? '+' : ''}${Math.abs(netProfit).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}
                  </div>
                  <div className="kpi-sub">
                    <span className={clsx('kpi-badge', roiPct >= 0 ? 'kpi-badge--up' : 'kpi-badge--down')}>
                      ROI {Math.abs(roiPct) > 1000000 ? 'Máximo' : `${roiPct >= 0 ? '+' : ''}${roiPct.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`}
                    </span>
                  </div>
                </div>
                <div className={clsx('kpi-card', winRatePct >= 50 ? 'kpi-card--positive' : 'kpi-card--negative')}>
                  <div className="kpi-label">Tasa de Victorias</div>
                  <div className="kpi-value font-data">{winRatePct.toFixed(1)}%</div>
                  <div className="metric-track">
                    <div className="h-full bg-[var(--c-positive)] transition-all" style={{ width: `${winRatePct}%` }} />
                  </div>
                  <div className="kpi-sub font-data mt-2">{tradeCount} operaciones</div>
                </div>
                <div className={clsx('kpi-card', pfValue >= 1.5 ? 'kpi-card--positive' : pfValue >= 1 ? 'kpi-card--neutral' : 'kpi-card--negative')}>
                  <div className="kpi-label">Factor de Beneficio</div>
                  <div className="kpi-value font-data">{pfValue.toFixed(2)}</div>
                  <div className="metric-track">
                    <div className="h-full bg-[var(--c-neutral)] transition-all" style={{ width: `${Math.min(pfValue * 30, 100)}%` }} />
                  </div>
                  <div className="kpi-sub font-data mt-2">Exp {expectancyR.toFixed(2)}R</div>
                </div>
                <div className="kpi-card kpi-card--negative">
                  <div className="kpi-label">Reducción Máxima</div>
                  <div className="kpi-value font-data" style={{color:'var(--c-negative)'}}>{maxDrawdownPct.toFixed(2)}%</div>
                  <div className="metric-track">
                    <div className="h-full bg-[var(--c-negative)] transition-all" style={{ width: `${Math.min(maxDrawdownPct * 5, 100)}%` }} />
                  </div>
                  <div className="kpi-sub font-data mt-2">${Math.abs(maxDrawdownCash).toFixed(2)}</div>
                </div>
                <div className="kpi-card kpi-card--neutral">
                  <div className="kpi-label">Equidad</div>
                  <div className="kpi-value font-data">${equity.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
                  <div className="metric-track">
                    <div className="h-full bg-[var(--c-accent)] transition-all" style={{ width: `${Math.min((equity / Math.max(1, balance)) * 100, 100)}%` }} />
                  </div>
                  <div className="kpi-sub font-data mt-2">Saldo ${balance.toLocaleString(undefined,{minimumFractionDigits:2})}</div>
                </div>
              </div>

              {/* Main Grid */}
              {tradeCount === 0 ? (
                <QuantSimulator 
                  initialBalance={balance} 
                  accountLogin={stats?.account_snapshot?.account_login ?? ''} 
                  serverName={stats?.account_snapshot?.server_name ?? ''} 
                />
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                  <div className="xl:col-span-2 space-y-4">
                    {/* Equity Chart */}
                    <div className="widget">
                      <div className="widget-header">
                        <div className="widget-title"><LineChart className="widget-title-icon" />Curva de Capital</div>
                        <span className="font-data text-sm font-bold" style={{color:'var(--c-neutral)'}}>
                          ${endEquity.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}
                        </span>
                      </div>
                      <div className="widget-body widget-full">
                        <EquityChart data={equityCurve} />
                      </div>
                    </div>
                    {/* Trade History */}
                    <TradeHistory data={history} onTradeClick={(t: TradeDetail) => setSelectedTrade(t)} />
                  </div>

                  {/* Right Column */}
                  <div className="space-y-4">
                    <div className="widget">
                      <div className="widget-header">
                        <div className="widget-title">
                          <TrendingUp className="widget-title-icon" />
                          Estrategia de Salud
                        </div>
                      </div>
                      <div className="widget-body">
                        <div className="metric-row">
                          <span className="metric-row-label">Expectativa</span>
                          <span className="metric-row-value font-data">
                            {expectancyR.toFixed(2)} R · ${expectancyCash.toFixed(2)}
                          </span>
                        </div>
                        <div className="metric-row">
                          <span className="metric-row-label">Promedio victorias/derrotas</span>
                          <span className="metric-row-value font-data">
                            ${avgWin.toFixed(2)} / ${avgLoss.toFixed(2)}
                          </span>
                        </div>
                        <div className="metric-row">
                          <span className="metric-row-label">Mantenimiento promedio</span>
                          <span className="metric-row-value font-data">
                            {(() => {
                              const mins = Math.floor(avgDuration);
                              const h = Math.floor(mins / 60);
                              const m = mins % 60;
                              return h > 0 ? `${h}h ${m}m` : `${m}m`;
                            })()}
                          </span>
                        </div>
                        <div className="metric-row">
                          <span className="metric-row-label">CAGR</span>
                          <span className="metric-row-value font-data">
                            {Math.abs(cagrPct) > 1000000 
                              ? '> 1,000,000%' 
                              : `${cagrPct.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`}
                          </span>
                        </div>
                        <div className="metric-row">
                          <span className="metric-row-label">ESCUADRÓN (SQN)</span>
                          <span className="metric-row-value font-data">
                            {(stats?.summary?.sqn ?? 0).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="widget">
                      <div className="widget-header"><div className="widget-title"><ShieldAlert className="widget-title-icon" style={{color:'var(--c-negative)'}} />Pulso de Riesgo</div></div>
                      <div className="widget-body">
                        <div className="metric-row"><span className="metric-row-label">Valor en Riesgo (VaR 99%)</span><span className="metric-row-value font-data">{Math.min(var95Pct, 100).toFixed(2)} %</span></div>
                        <div className="metric-row"><span className="metric-row-label">Riesgo de Cola (CVaR)</span><span className="metric-row-value font-data">{Math.min(cvarPct, 100).toFixed(2)} %</span></div>
                        <div className="metric-row"><span className="metric-row-label">Volatilidad Diaria</span><span className="metric-row-value font-data">{Math.min(dailyVolPct, 100).toFixed(2)} %</span></div>
                        <div className="metric-row"><span className="metric-row-label">Volatilidad Descendente</span><span className="metric-row-value font-data">{Math.min(downsideVolPct, 100).toFixed(2)} %</span></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {activeTab === 'Data Journal' && <DataJournal data={history} quant={stats?.quant} onAskAi={({focus,prompt}) => openAiAnalyst(focus,prompt)} />}
          {activeTab === 'Centro de Control' && <ControlCenter stats={stats} selectedBot={selectedBot} view="home" />}
          {activeTab === 'Temporal Dynamics' && <TemporalDynamics trades={history} equityCurve={equityCurve} />}
          {activeTab === 'Risk Analytics' && stats?.quant && (
            <RiskAnalytics quant={stats.quant} risk={stats.risk} perf={stats.perf}
              returns={riskReturnSeries}
              onAskAi={({focus,prompt}) => openAiAnalyst(focus,prompt)} />
          )}
          {activeTab === 'Analista IA' && (
            <AIAnalystPanel
              stats={stats}
              selectedBot={selectedBot}
              accountLogin={selectedAccountLogin}
              serverName={selectedAccountServer}
              seed={aiSeed}
            />
          )}
          {activeTab === 'Macro Intel' && (
            <MacroNewsPanel
              key={`${journalAccountLogin ?? 'none'}:${journalServerName ?? 'none'}`}
              accountLogin={journalAccountLogin}
              serverName={journalServerName}
              onAskAi={({focus,prompt}) => openAiAnalyst(focus,prompt)}
            />
          )}
          {activeTab === 'Trading Journal' && (
            <TradingJournal
              key={`${journalAccountLogin ?? 'none'}:${journalServerName ?? 'none'}`}
              behavior={stats?.behavior}
              accountLogin={journalAccountLogin}
              serverName={journalServerName}
            />
          )}

          {activeTab === 'Ajustes' && (
            <motion.div initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} className="space-y-6 max-w-lg">
              <div className="widget">
                <div className="widget-header"><div className="widget-title"><Settings className="widget-title-icon" />Terminal Preferences</div></div>
                <div className="widget-body space-y-3">
                  {([
                    {id:'dark' as const,label:'Deep Space',hint:'High contrast dark',icon:Moon},
                    {id:'light' as const,label:'Daylight',hint:'Clean workspace',icon:Sun},
                    {id:'gold' as const,label:'Luxury Gold',hint:'Premium presentation',icon:Crown},
                  ]).map(o => {
                    const I = o.icon; const a = theme === o.id
                    return (
                      <button key={o.id} onClick={() => setTheme(o.id)}
                        className={clsx('w-full flex items-center justify-between gap-3 px-4 py-3 rounded-lg border transition-all text-left',
                          a ? 'border-[var(--c-neutral)] bg-[var(--c-neutral-dim)]' : 'border-[var(--bg-border)] bg-[var(--bg-surface)] hover:border-[var(--bg-border-strong)]')}>
                        <div className="flex items-center gap-3">
                          <I className={clsx('w-4 h-4', a ? 'text-[var(--c-neutral)]' : 'text-[var(--text-muted)]')} />
                          <div>
                            <p className="text-xs font-bold uppercase tracking-wider">{o.label}</p>
                            <p className="text-[10px]" style={{color:'var(--text-muted)'}}>{o.hint}</p>
                          </div>
                        </div>
                        {a && <span className="text-[9px] uppercase font-black" style={{color:'var(--c-neutral)'}}>Active</span>}
                      </button>
                    )
                  })}
                </div>
              </div>
              <div className="widget" style={{borderColor:'rgba(239,68,68,0.1)'}}>
                <div className="widget-header"><div className="widget-title">Risk Kill-Switch</div></div>
                <div className="widget-body grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg" style={{background:'var(--bg-void)'}}>
                    <p className="text-[9px] uppercase font-bold" style={{color:'var(--text-ghost)'}}>Max Drawdown</p>
                    <p className="text-lg font-black font-data" style={{color:'var(--c-negative)'}}>10.0%</p>
                  </div>
                  <div className="p-4 rounded-lg" style={{background:'var(--bg-void)'}}>
                    <p className="text-[9px] uppercase font-bold" style={{color:'var(--text-ghost)'}}>Max Vol (Daily)</p>
                    <p className="text-lg font-black font-data" style={{color:'var(--c-warning)'}}>2.5%</p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          <TradeDetailDrawer trade={selectedTrade} onClose={() => setSelectedTrade(null)} />
        </div>
      </main>
    </div>
  )
}
