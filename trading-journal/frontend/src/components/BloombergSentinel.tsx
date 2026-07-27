'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { ShieldAlert, Brain, TrendingUp, Info, Activity, Terminal, Zap, Globe, Lock } from 'lucide-react'
import { clsx } from 'clsx'

import { buildApiUrl } from '@/lib/api'

export interface BloombergData {
  stress_prob: number
  narrative: string
  weights: Record<string, number>
  status: 'online'  'offline'  'degraded'  'stale'  'error'
  health_status?: 'healthy'  'degraded'  'stale'  'offline'
  data_age_seconds?: number  null
  ttl_seconds?: number
  context_id?: string
  model_version?: string
  feature_version?: string
  account_login?: string
  server_name?: string
  fallback_active?: boolean
  scope_status?: 'account_verified'  'recalibrating'
  market_baseline_account?: string  null
  source_health?: Record<string, { status?: string; age_seconds?: number  null }>
  entropy?: number
  confidence?: number
  dominant_theme?: string
  updated_at?: string
  xi?: number
  lambda_dominant?: number
  entropy_spectral?: number
  mtl?: number
  kld?: number
  top_highest_corr?: Array<{ asset_a?: string, asset_b?: string, pair?: string, corr: number }>
  top_lowest_corr?: Array<{ asset_a?: string, asset_b?: string, pair?: string, corr: number }>
  universe_version?: string
  dataset_hash?: string
  data_provider?: string
  data_frequency?: string
  data_coverage?: number
  pct_imputed?: number
  observations?: number
  data_status?: 'fresh'  'cached'  'degraded'  'unavailable'
  shadow_mode?: boolean
  approval_status?: 'pending'  'approved'  'rejected'  'blocked'
  alternative_scenario?: string
  invalidation_conditions?: string
  evidence?: string
  account_implications?: string
  decision?: {
    status?: string
    weights?: Record<string, number>
    current_exposures?: { data_quality?: string; gross_exposure?: number; net_exposure?: number }
  }
  stress_tests?: { worst_case_return?: number; worst_case_pnl?: number; approval_gate_passed?: boolean }
}

export default function BloombergSentinel({ data: initialData, colsClass = "grid-cols-1 sm:grid-cols-2", minimal = false, accountLogin, serverName }: { data?: BloombergData, colsClass?: string, minimal?: boolean, accountLogin?: string  null, serverName?: string  null }) {
  const [data, setData] = React.useState<BloombergData  undefined>(initialData)
  
  React.useEffect(() => {
    if (initialData) {
      setData(initialData)
      return
    }

    const fetchData = async () => {
      try {
        const res = await fetch(buildApiUrl('/bloomberg/latest', { account_login: accountLogin, server_name: serverName }))
        if (res.ok) {
          const d = await res.json()
          setData(d)
        }
      } catch (e) {
        console.error("Sentinel fetch error:", e)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [initialData, accountLogin, serverName])

  const isOffline = !data  data.status === 'offline'
  const safeNumber = (value: unknown, fallback = 0) => {
    const n = Number(value)
    return Number.isFinite(n) ? n : fallback
  }
  const titleCase = (value: string) =>
    value
      .replace(/[_-]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/\b\w/g, (c) => c.toUpperCase())

  const stressLevel = Math.max(0, Math.min(100, safeNumber(data?.stress_prob) * 100))
  const entropy = safeNumber(data?.entropy, 0.42)
  const confidence = Math.max(0, Math.min(100, safeNumber(data?.confidence, 0) * 100))
  const marketBias = titleCase(data?.dominant_theme  'Stable')
  const healthStatus = data?.health_status  (isOffline ? 'offline' : 'degraded')
  const crisisState = data?.model_version ? safeNumber(data?.xi) : safeNumber(data?.stress_prob)
  const allocationWeights = Object.keys(data?.weights  {}).length > 0
    ? data?.weights  {}
    : data?.decision?.weights  {}
  const dataCoverageLabel = typeof data?.data_coverage === 'number' ? `${data.data_coverage.toFixed(1)}%` : 'Awaiting cycle'
  const observationsLabel = typeof data?.observations === 'number' ? String(data.observations) : 'Awaiting cycle'
  const approvalLabel = data?.approval_status === 'approved'
    ? 'Reviewed'
    : data?.approval_status === 'blocked'
      ? healthStatus === 'stale' ? 'Blocked · account stale' : 'Blocked · risk gate'
      : 'Review pending'
  const correlationLabel = (item: { asset_a?: string; asset_b?: string; pair?: string }) => {
    if (item.asset_a && item.asset_b) return `${item.asset_a} ↔ ${item.asset_b}`
    return (item.pair  'N/D').replace('-', ' ↔ ')
  }

  const getStressColor = (val: number) => {
    if (val > 70) return 'text-[var(--c-negative)]'
    if (val > 40) return 'text-[var(--c-warning)]'
    return 'text-[var(--c-positive)]'
  }

  const getStatusLabel = () => {
    if (isOffline) return 'SYNCING GLOBAL ENGINES...'
    if (healthStatus === 'stale') return 'STALE DATA: DECISIONS DISABLED'
    if (healthStatus === 'degraded') return 'DEGRADED: PARTIAL DATA COVERAGE'
    if (stressLevel > 70) return 'SYSTEM ALERT: HIGH VOLATILITY REGIME'
    if (stressLevel > 40) return 'CAUTION: REGIME TRANSITION DETECTED'
    return 'STATUS: NOMINAL / LOW STRESS'
  }

  return (
    <div className="widget h-full flex flex-col p-0 overflow-hidden relative group">
      {/* Top Scanner Line (Animation) */}
      <motion.div 
        initial={{ top: 0 }}
        animate={{ top: '100%' }}
        transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
        className="absolute left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[var(--c-neutral)] to-transparent opacity-20 z-10 pointer-events-none"
      />

      {/* Header Area */}
      <div className="p-6 pb-4 border-b border-[var(--bg-border)] bg-gradient-to-b from-[var(--bg-elevated)] to-transparent">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <div className="relative">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-[var(--bg-void)] border border-[var(--bg-border-strong)] overflow-hidden">
                <Terminal className="w-6 h-6 text-[var(--c-neutral)]" />
                <motion.div 
                  animate={{ opacity: [0.1, 0.3, 0.1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="absolute inset-0 bg-[var(--c-neutral-dim)]"
                />
              </div>
              <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-[var(--bg-base)] bg-[var(--c-positive)] shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
            </div>
            
            <div className="min-w-0">
              <h3 className="flex flex-wrap items-center gap-2 text-sm font-black uppercase italic leading-tight text-[var(--text-primary)] sm:text-base">
                <span>Sentinel Intelligence</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--bg-surface)] border border-[var(--bg-border)] text-[var(--text-muted)] not-italic">V2.4 CLOUD</span>
              </h3>
              <div className="flex items-center gap-2 mt-1">
                <Globe className="w-3 h-3 shrink-0 text-[var(--text-muted)]" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] leading-snug">
                  {getStatusLabel()}
                </span>
              </div>
            </div>
          </div>

          <div className="shrink-0 text-left sm:text-right">
             <div className="mb-2 flex flex-wrap justify-start gap-1.5 sm:justify-end">
               {data?.shadow_mode && <span className="rounded border border-[var(--c-warning)]/40 bg-[var(--c-warning)]/10 px-2 py-1 text-[8px] font-black uppercase tracking-wider text-[var(--c-warning)]">Shadow Mode</span>}
               {data?.data_status && <span className="rounded border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2 py-1 text-[8px] font-black uppercase tracking-wider text-[var(--text-muted)]">Data {data.data_status}</span>}
             </div>
             <div className={clsx(
               "flex items-center justify-end gap-2 text-[10px] font-bold mb-1",
               healthStatus === 'healthy' ? 'text-[var(--c-positive)]' : healthStatus === 'stale' ? 'text-[var(--c-negative)]' : 'text-[var(--c-warning)]'
             )}>
                <Zap className="w-3 h-3" />
                {healthStatus.toUpperCase()}
             </div>
             {data?.updated_at && (
                <span className="text-[9px] font-data text-[var(--text-muted)]">
                  LAST PULSE: {new Date(data.updated_at).toLocaleTimeString()}
                </span>
             )}
             {typeof data?.data_age_seconds === 'number' && (
               <div className="mt-1 text-[8px] font-data uppercase text-[var(--text-muted)]">
                 AGE {data.data_age_seconds}s {data.model_version ? `· MODEL ${data.model_version}` : ''}
               </div>
             )}
          </div>
        </div>
        {data?.scope_status === 'recalibrating' && (
          <div className="mt-4 rounded-lg border border-[var(--c-warning)]/25 bg-[var(--c-warning)]/5 px-3 py-2 text-[10px] font-bold text-[var(--c-warning)]">
            Market intelligence is current. Account allocation is recalibrating for {accountLogin  'the selected account'}; no weights from another account are displayed.
          </div>
        )}
      </div>

      <div className="flex-1 p-5 sm:p-6 space-y-6 overflow-y-auto custom-scrollbar">
        <div className="rounded-2xl border border-[var(--bg-border-strong)] bg-[linear-gradient(135deg,rgba(79,140,255,0.12),rgba(16,25,37,0.92)_45%,rgba(234,179,8,0.05))] p-4 shadow-[var(--shadow-card)] sm:p-5">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[9px] font-black uppercase tracking-[0.22em] text-[var(--c-neutral)]">Unified Institutional Read</p>
              <p className="mt-1 text-sm font-bold text-[var(--text-primary)]">Régimen, estructura sistémica y cartera en una sola decisión</p>
            </div>
            <span className="rounded-full border border-[var(--c-warning)]/30 bg-[var(--c-warning-dim)] px-3 py-1 text-[9px] font-black uppercase tracking-wider text-[var(--c-warning)]">Execution disabled · Shadow</span>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <SummaryCell label="Crisis forecast 5m" value={`${stressLevel.toFixed(1)}%`} tone={stressLevel > 60 ? 'negative' : stressLevel > 35 ? 'warning' : 'positive'} />
            <SummaryCell label="Current high-vol state" value={`${Math.max(0, Math.min(100, crisisState * 100)).toFixed(1)}%`} tone="info" />
            <SummaryCell label="Portfolio stance" value={allocationWeights.CASH != null ? `${(safeNumber(allocationWeights.CASH) * 100).toFixed(0)}% cash` : 'Cycle pending'} tone="warning" />
            <SummaryCell label="Worst stress case" value={typeof data?.stress_tests?.worst_case_return === 'number' ? `${(data.stress_tests.worst_case_return * 100).toFixed(1)}%` : 'Cycle pending'} tone="neutral" />
          </div>
        </div>

        {/* Core Metrics Dashboard */}
        <div className={clsx("grid gap-3", colsClass)}>
          <MetricCard 
            icon={<ShieldAlert className={clsx("w-4 h-4", getStressColor(stressLevel))} />}
            label="Structural Risk (HMM)"
            value={`${stressLevel.toFixed(1)}%`}
            subLabel={stressLevel > 60 ? 'ADVERSE REGIME' : stressLevel > 35 ? 'TRANSITION WATCH' : 'LOW STRESS REGIME'}
            tooltip="Probabilidad de que el mercado esté en un régimen de alta volatilidad (Stress)."
          />
          <MetricCard 
            icon={<Activity className="w-4 h-4 text-[var(--c-neutral)]" />}
            label="Market Uncertainty"
            value={entropy.toFixed(2)}
            subLabel="MODEL ENTROPY"
            tooltip="Nivel de desorden o indecisión en los datos macro actuales."
          />
          <MetricCard 
            icon={<Brain className="w-4 h-4 text-[var(--c-info)]" />}
            label="Narrative Confidence"
            value={confidence > 0 ? `${confidence.toFixed(0)}%` : 'N/D'}
            subLabel="NOT HISTORICAL ACCURACY"
            tooltip="Confianza de la lectura actual. No representa precisión histórica hasta completar evaluación fuera de muestra."
          />
          <MetricCard 
            icon={<TrendingUp className="w-4 h-4 text-[var(--c-positive)]" />}
            label="Market Bias"
            value={marketBias}
            subLabel="SENTIMENT TREND"
            isText
            tooltip="Tema predominante detectado en las noticias y redes sociales."
          />
        </div>

        {/* Mirofish Narrative Panel */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--c-neutral)]" />
              <span className="text-[10px] uppercase font-black tracking-[0.2em] text-[var(--text-muted)]">Narrative Swarm (Mirofish)</span>
            </div>
            <div className="flex items-center gap-2">
               <div className="w-2 h-2 rounded-full border border-[var(--c-neutral)] opacity-50 animate-ping" />
               <span className="text-[8px] font-bold text-[var(--c-neutral)]">ANALYZING 40+ FEEDS</span>
            </div>
          </div>
          
          <div className="relative p-5 rounded-2xl border border-[var(--bg-border)] bg-[var(--bg-surface)] backdrop-blur-sm">
            <div className="absolute top-4 left-4 opacity-5 text-[var(--text-primary)]">
               <Info className="w-12 h-12" />
            </div>
            <p className="text-sm leading-relaxed text-[var(--text-secondary)] font-medium italic relative z-10">
              &quot;{data?.narrative  'Orchestrating engrams. Correlating structural price action with global macro liquidity cycles...'}&quot;
            </p>
          </div>
        </div>

        {!minimal && (
          <>
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-[var(--bg-border)] bg-[var(--bg-border)] text-[9px] uppercase tracking-wider text-[var(--text-muted)] sm:grid-cols-4">
              <DataCell value={data?.data_provider  'Market feed pending'} label="Provider" />
              <DataCell value={dataCoverageLabel} label="Coverage" />
              <DataCell value={observationsLabel} label="Observations" />
              <DataCell value={approvalLabel} label="Governance" />
            </div>

            {/* Advanced Topological & Spectral Risk */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-[var(--c-neutral)]" />
                <span className="text-[10px] uppercase font-black tracking-[0.2em] text-[var(--text-muted)]">Topological & Spectral Risk</span>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <MetricCard 
                  icon={<Zap className="w-4 h-4 text-[var(--c-neutral)]" />}
                  label="Current Crisis State"
                  value={`${Math.max(0, Math.min(100, crisisState * 100)).toFixed(1)}%`}
                  subLabel="HMM HIGH-VOL REGIME"
                  tooltip="Probabilidad filtrada del estado actual de alta volatilidad."
                />
                <MetricCard 
                  icon={<TrendingUp className="w-4 h-4 text-[var(--c-warning)]" />}
                  label="Dominant Eigenvalue"
                  value={safeNumber(data?.lambda_dominant).toFixed(3)}
                  subLabel="RANDOM MATRIX THEORY"
                  tooltip="Dominant eigenvalue (lambda_max) capturing system-wide dimensional contraction."
                />
                <MetricCard 
                  icon={<Activity className="w-4 h-4 text-[var(--c-info)]" />}
                  label="Spectral Entropy"
                  value={safeNumber(data?.entropy_spectral).toFixed(3)}
                  subLabel="DIVERGENCE SHIFT"
                  tooltip="Entropy of the covariance eigenspectrum (captures complexity collapse)."
                />
                <MetricCard 
                  icon={<Globe className="w-4 h-4 text-[var(--c-positive)]" />}
                  label="TDA Contract. (MTL)"
                  value={safeNumber(data?.mtl).toFixed(3)}
                  subLabel="TOPOLOGICAL LENGTH"
                  tooltip="Mean topological length of the Minimum Spanning Tree (MST)."
                />
                <MetricCard 
                  icon={<Activity className="w-4 h-4 text-[var(--c-neutral)]" />}
                  label="KLD Divergence"
                  value={safeNumber(data?.kld).toFixed(4)}
                  subLabel="INFORMATION SHIFT"
                  tooltip="Kullback-Leibler divergence of covariance structure against benchmark."
                />
              </div>
            </div>

            {/* Highest and Lowest Correlation Pairs */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                 <Brain className="w-3.5 h-3.5 text-[var(--c-info)]" />
                 <span className="text-[10px] uppercase font-black tracking-[0.2em] text-[var(--text-muted)]">MST Correlation Hub (N=26)</span>
              </div>
              
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                 {/* Highest Correlation Pairs */}
                 <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-void)] p-4 space-y-3">
                    <div className="text-[10px] font-black uppercase text-[var(--c-negative)] tracking-wider flex items-center justify-between">
                       <span>Systemic Coupling (Highest)</span>
                       <span className="h-1.5 w-1.5 rounded-full bg-[var(--c-negative)] animate-pulse" />
                    </div>
                    <div className="space-y-2">
                       {data?.top_highest_corr && data.top_highest_corr.length > 0 ? (
                          data.top_highest_corr.slice(0, 5).map((item, idx) => (
                             <div key={idx} className="flex justify-between items-center py-1.5 border-b border-[var(--bg-border)] last:border-0 text-xs">
                                <span className="font-semibold text-[var(--text-primary)]">{correlationLabel(item)}</span>
                                <span className="font-data font-bold text-[var(--c-negative)]">{safeNumber(item.corr) >= 0 ? '+' : ''}{safeNumber(item.corr).toFixed(3)}</span>
                             </div>
                          ))
                       ) : (
                          <span className="text-[10px] text-[var(--text-muted)]">No data available</span>
                       )}
                    </div>
                 </div>

                 {/* Lowest Correlation Pairs */}
                 <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-void)] p-4 space-y-3">
                    <div className="text-[10px] font-black uppercase text-[var(--c-positive)] tracking-wider flex items-center justify-between">
                       <span>Diversification Pairs (Lowest)</span>
                       <span className="h-1.5 w-1.5 rounded-full bg-[var(--c-positive)]" />
                    </div>
                    <div className="space-y-2">
                       {data?.top_lowest_corr && data.top_lowest_corr.length > 0 ? (
                          data.top_lowest_corr.slice(0, 5).map((item, idx) => (
                             <div key={idx} className="flex justify-between items-center py-1.5 border-b border-[var(--bg-border)] last:border-0 text-xs">
                                <span className="font-semibold text-[var(--text-primary)]">{correlationLabel(item)}</span>
                                <span className="font-data font-bold text-[var(--c-positive)]">{safeNumber(item.corr) >= 0 ? '+' : ''}{safeNumber(item.corr).toFixed(3)}</span>
                             </div>
                          ))
                       ) : (
                          <span className="text-[10px] text-[var(--text-muted)]">No data available</span>
                       )}
                    </div>
                 </div>
              </div>
            </div>

            {/* Institutional Weights (Black-Litterman) */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Lock className="w-3.5 h-3.5 text-[var(--c-warning)]" />
                <span className="text-[10px] uppercase font-black tracking-[0.2em] text-[var(--text-muted)]">Institutional Allocation Model</span>
              </div>
              
              <div className="grid grid-cols-1 gap-x-8 gap-y-5 rounded-xl border border-[var(--bg-border)] bg-[var(--bg-void)] p-5 sm:grid-cols-2">
                {Object.entries(allocationWeights).length > 0 ? (
                  Object.entries(allocationWeights).map(([asset, weight]) => (
                    <div key={asset} className="group/item">
                      <div className="flex justify-between items-end mb-2">
                        <span className="text-xs font-black tracking-widest text-[var(--text-primary)]">{asset}</span>
                        <span className="text-xs font-data font-bold text-[var(--c-neutral)]">{(safeNumber(weight) * 100).toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-[var(--bg-surface)] rounded-full overflow-hidden">
                        <motion.div 
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max(0, Math.min(100, safeNumber(weight) * 100))}%` }}
                          transition={{ duration: 1, ease: "circOut" }}
                          className="h-full bg-gradient-to-r from-[var(--c-neutral-dim)] to-[var(--c-neutral)]"
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="col-span-2 py-8 flex flex-col items-center justify-center gap-3 opacity-40">
                    <Activity className="w-6 h-6 animate-pulse text-[var(--text-primary)]" />
                    <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[var(--text-secondary)]">Waiting for verified Sentinel cycle</span>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Footer Visual Decor */}
      <div className="h-2 bg-gradient-to-r from-transparent via-[var(--c-neutral)] to-transparent opacity-10" />
    </div>
  )
}

function SummaryCell({ label, value, tone }: { label: string; value: string; tone: 'positive'  'negative'  'warning'  'info'  'neutral' }) {
  const tones = {
    positive: 'text-[var(--c-positive)]',
    negative: 'text-[var(--c-negative)]',
    warning: 'text-[var(--c-warning)]',
    info: 'text-[var(--c-neutral)]',
    neutral: 'text-[var(--text-primary)]',
  }
  return (
    <div className="rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)] p-3">
      <p className="text-[8px] font-black uppercase tracking-[0.16em] text-[var(--text-muted)]">{label}</p>
      <p className={clsx('mt-1 font-data text-base font-black', tones[tone])}>{value}</p>
    </div>
  )
}

function DataCell({ value, label }: { value: string; label: string }) {
  return (
    <div className="min-w-0 bg-[var(--bg-elevated)] p-3.5">
      <span className="block truncate font-black normal-case tracking-normal text-[var(--text-primary)]">{value}</span>
      <span className="mt-1 block">{label}</span>
    </div>
  )
}

function MetricCard({ icon, label, value, subLabel, isText = false, tooltip }: { icon: React.ReactNode, label: string, value: string, subLabel: string, isText?: boolean, tooltip?: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-[var(--bg-border)] bg-[var(--bg-surface)] p-3 transition-all hover:border-[var(--bg-border-strong)] group/card cursor-help" title={tooltip}>
      <div className="flex items-center gap-2 mb-2">
        <div className="shrink-0 p-1.5 rounded-lg bg-[var(--bg-void)] border border-[var(--bg-border-strong)] group-hover/card:scale-110 transition-transform">
          {icon}
        </div>
        <span className="min-w-0 truncate text-[9px] uppercase font-black tracking-wider leading-tight text-[var(--text-muted)]">{label}</span>
      </div>
      <div className={clsx("min-w-0 font-black text-[var(--text-primary)]", isText ? "truncate text-xs uppercase tracking-normal" : "text-xl font-data tracking-tight")}>
        {value}
      </div>
      <div className="truncate text-[8px] font-bold text-[var(--text-muted)] uppercase mt-1 tracking-widest">{subLabel}</div>
    </div>
  )
}
