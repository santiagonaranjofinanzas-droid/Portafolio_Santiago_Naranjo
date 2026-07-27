'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, ArrowUpRight, ArrowDownRight, Clock, Target, ShieldAlert, DollarSign, BarChart2, Zap } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import TradeM1Chart from './TradeM1Chart'
import { buildApiUrl } from '@/lib/api'

export interface TradeDetail {
  position_id?: number
  symbol: string
  direction: 'Buy'  'Sell'  string
  entrytime: string
  exittime: string
  volume: number
  netpnl: number
  r_multiple: number
  exit_reason?: number
  entryprice: number
  exitprice: number
  sl: number
  commission: number
  risk_price: number
  gross_pnl: number
  swap: number
  mfe_r?: number  null
  mae_r?: number  null
  tw_mfe_r?: number  null
  tw_mae_r?: number  null
  efficiency?: number  null
  mae?: number  null
  mfe?: number  null
  excursion_source?: string  null
  excursion_timeframe?: string  null
  excursion_samples?: number  null
  excursion_coverage?: number  null
  risk_basis?: string  null
  magic_number?: number  null
  planned_tp?: number  null
  planned_max_r?: number  null
  what_if_result?: string  null
  what_if_pnl?: number  null
  what_if_r?: number  null
  r_multiple_adj?: number  null
  execution_slippage_cash?: number  null
  execution_slippage_r?: number  null
  conditional_vol?: number  null
}

interface TradeDetailDrawerProps {
  trade: TradeDetail  null
  onClose: () => void
}

const EXIT_LABELS: Record<number, { label: string; color: string }> = {
  2: { label: 'Stop Loss', color: 'text-rose-400' },
  3: { label: 'Take Profit', color: 'text-emerald-400' },
  4: { label: 'Stop Loss', color: 'text-rose-400' },
  5: { label: 'Take Profit', color: 'text-emerald-400' },
}

function InfoRow({ label, value, valueClass = 'text-[var(--text-secondary)]' }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="stat-row">
      <span className="text-[var(--text-muted)] text-xs">{label}</span>
      <span className={`font-data text-sm font-medium ${valueClass}`}>{value}</span>
    </div>
  )
}

export default function TradeDetailDrawer({ trade, onClose }: TradeDetailDrawerProps) {
  const { data: chartData, isLoading } = useQuery({
    queryKey: ['trade-chart', trade?.position_id],
    queryFn: async () => {
      if (!trade) return null
      const parseUTC = (str: string) => {
        return Math.floor(new Date(str.endsWith('Z') ? str : str + 'Z').getTime() / 1000)
      }
      const entryTs = parseUTC(trade.entrytime)
      const exitTs = parseUTC(trade.exittime)
      const res = await fetch(buildApiUrl('/trade/chart', { symbol: trade.symbol, entry: entryTs, exit: exitTs }))
      if (!res.ok) throw new Error('Chart Sync Failed')
      return res.json()
    },
    enabled: !!trade
  })

  const { data: journalPayload } = useQuery({
    queryKey: ['trade-journal', trade?.position_id],
    queryFn: async () => {
      if (!trade?.position_id) return null
      const res = await fetch(buildApiUrl(`/journal/${trade.position_id}`))
      if (!res.ok) throw new Error('Journal Sync Failed')
      return res.json()
    },
    enabled: !!trade?.position_id
  })

  const journalData = journalPayload?.journal

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.08
      }
    }
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 260, damping: 26 } }
  }

  const exitInfo = trade ? (EXIT_LABELS[trade.exit_reason ?? -1] ?? { label: 'Manual', color: 'text-slate-400' }) : null
  const isProfit = (trade?.netpnl ?? 0) >= 0

  return (
    <AnimatePresence>
      {trade && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(7,9,14,0.75)', backdropFilter: 'blur(6px)' }}
          />

          {/* Drawer Panel */}
          <motion.div
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 30, stiffness: 300, mass: 0.8 }}
            className="fixed right-0 top-0 h-full z-50 overflow-y-auto"
            style={{
              width: '100%',
              maxWidth: 680,
              background: 'var(--bg-elevated)',
              borderLeft: '1px solid var(--bg-border-strong)',
              boxShadow: '-8px 0 40px rgba(0,0,0,0.6), -1px 0 0 rgba(59,130,246,0.08)'
            }}
          >
            {/* Top accent bar */}
            <div style={{
              height: 2,
              background: isProfit
                ? 'linear-gradient(90deg, transparent, #10B981, #3B82F6, transparent)'
                : 'linear-gradient(90deg, transparent, #F43F5E, #8B5CF6, transparent)'
            }} />

            <div className="p-8">
              {/* ── Header ── */}
              <div className="flex items-start justify-between mb-8">
                <div className="flex items-center gap-4">
                  {/* Direction badge */}
                  <div className="relative">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${isProfit ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}
                      style={{ border: `1px solid ${isProfit ? 'rgba(16,185,129,0.25)' : 'rgba(244,63,94,0.25)'}` }}>
                      {trade.direction === 'Buy'
                        ? <ArrowUpRight className={`w-6 h-6 ${isProfit ? 'text-emerald-400' : 'text-emerald-400'}`} />
                        : <ArrowDownRight className={`w-6 h-6 ${isProfit ? 'text-orange-400' : 'text-rose-400'}`} />
                      }
                    </div>
                    <div className={`absolute -top-1 -right-1 w-3 h-3 rounded-full ${isProfit ? 'bg-emerald-500' : 'bg-rose-500'}`}
                      style={{ boxShadow: isProfit ? '0 0 8px rgba(16,185,129,0.6)' : '0 0 8px rgba(244,63,94,0.6)' }} />
                  </div>

                  <div>
                    <div className="flex items-baseline gap-3">
                      <h2 className="text-xl font-bold text-[var(--text-primary)] tracking-tight">{trade.symbol}</h2>
                      <span className="font-data text-[var(--text-muted)] text-sm">#{trade.position_id}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full ${trade.direction === 'Buy' ? 'bg-blue-500/15 text-blue-400' : 'bg-orange-500/15 text-orange-400'}`}>
                        {trade.direction}
                      </span>
                      <span className="text-[var(--text-muted)] text-xs font-data">{trade.volume} lots</span>
                      <span className="text-[var(--text-ghost)]">·</span>
                      <span className="text-[var(--text-muted)] text-xs">
                        {(() => {
                          const clean = trade.entrytime.replace(' ', 'T')
                          const d = new Date(clean.endsWith('Z') ? clean : clean + 'Z')
                          return d.toLocaleDateString('es-ES', { 
                            day: 'numeric', 
                            month: 'short', 
                            hour: '2-digit', 
                            minute: '2-digit',
                            timeZone: 'UTC'
                          })
                        })()}
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={onClose}
                  className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all"
                  style={{ background: 'var(--bg-void)', border: '1px solid var(--bg-border)' }}
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* ── KPI Strip ── */}
              <div className="grid grid-cols-3 gap-3 mb-8">
                {[
                  {
                    label: 'Net P&L',
                    value: `${isProfit ? '+' : ''}$${trade.netpnl?.toFixed(2)}`,
                    icon: DollarSign,
                    color: isProfit ? '#10B981' : '#F43F5E',
                    bg: isProfit ? 'rgba(16,185,129,0.08)' : 'rgba(244,63,94,0.08)',
                    border: isProfit ? 'rgba(16,185,129,0.2)' : 'rgba(244,63,94,0.2)'
                  },
                  {
                    label: 'R-Multiple',
                    value: `${trade.r_multiple?.toFixed(3)}R`,
                    icon: BarChart2,
                    color: '#60A5FA',
                    bg: 'rgba(59,130,246,0.08)',
                    border: 'rgba(59,130,246,0.2)'
                  },
                  {
                    label: 'Exit Reason',
                    value: exitInfo?.label ?? 'Manual',
                    icon: Zap,
                    color: exitInfo?.color?.replace('text-', '') === 'rose-400' ? '#F87171' : '#34D399',
                    bg: 'rgba(255,255,255,0.04)',
                    border: 'rgba(255,255,255,0.08)'
                  }
                ].map(({ label, value, icon: Icon, color, bg, border }) => (
                  <div key={label} className="rounded-xl p-4 flex flex-col gap-2"
                    style={{ background: bg, border: `1px solid ${border}` }}>
                    <div className="flex items-center gap-1.5">
                      <Icon className="w-3 h-3" style={{ color }} />
                      <p className="label-xs">{label}</p>
                    </div>
                    <p className="font-data font-bold text-lg leading-none" style={{ color }}>{value}</p>
                  </div>
                ))}
              </div>

              {/* ── M1 Chart Section ── */}
              <section className="mb-8">
                <div className="flex items-center gap-2 mb-4">
                  <Clock className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                  <h3 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest">Intraday Price Audit (M1)</h3>
                  <div className="flex-1 divider" style={{ borderColor: 'var(--bg-border)' }} />
                  <span className="text-[10px] text-[var(--text-muted)] font-data">{chartData?.length ?? 0} bars</span>
                </div>

                {isLoading ? (
                  <div className="h-64 flex items-center justify-center rounded-xl"
                    style={{ background: 'var(--bg-surface)', border: '1px dashed var(--bg-border-strong)' }}>
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-7 h-7 rounded-full animate-spin"
                        style={{ border: '2px solid rgba(59,130,246,0.15)', borderTopColor: '#3B82F6' }} />
                      <p className="text-xs text-[var(--text-muted)]">Fetching MT5 candles...</p>
                    </div>
                  </div>
                ) : (
                  <TradeM1Chart data={chartData} trade={trade} />
                )}
              </section>

              {/* ── Execution Details ── */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <h3 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest">Execution Details</h3>
                  <div className="flex-1 divider" style={{ borderColor: 'var(--bg-border)' }} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {/* Left: Prices */}
                  <div className="rounded-xl p-4"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--bg-border)' }}>
                    <div className="flex items-center gap-2 mb-3">
                      <Target className="w-3 h-3 text-[var(--text-muted)]" />
                      <p className="label-xs text-[var(--text-secondary)]">Execution</p>
                    </div>
                    <InfoRow label="Entry Price" value={trade.entryprice?.toFixed(5)} />
                    <InfoRow label="Exit Price" value={trade.exitprice?.toFixed(5)} />
                    <InfoRow label="Stop Loss" value={trade.sl > 0 ? trade.sl.toFixed(5) : 'None'} valueClass="text-rose-400/70" />
                    <InfoRow label="Commission" value={`$${trade.commission?.toFixed(2)}`} valueClass="text-slate-500" />
                    <InfoRow label="Volume" value={`${trade.volume} lots`} />
                    <InfoRow
                      label="Duration"
                      value={(() => {
                        const parseUTC = (str: string) => {
                          const clean = str.replace(' ', 'T')
                          return new Date(clean.endsWith('Z') ? clean : clean + 'Z').getTime()
                        }
                        const ms = parseUTC(trade.exittime) - parseUTC(trade.entrytime)
                        const mins = Math.floor(ms / 60000)
                        return mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h ${mins % 60}m`
                      })()}
                    />
                  </div>

                  {/* Right: Risk */}
                  <div className="rounded-xl p-4"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--bg-border)' }}>
                    <div className="flex items-center gap-2 mb-3">
                      <ShieldAlert className="w-3 h-3 text-[var(--text-muted)]" />
                      <p className="label-xs text-[var(--text-secondary)]">Risk Profile</p>
                    </div>
                    <InfoRow
                      label="Risk Price (R)"
                      value={trade.risk_price > 0 ? `${trade.risk_price?.toFixed(3)} pts` : 'No SL'}
                      valueClass="text-[var(--text-secondary)]"
                    />
                    <InfoRow
                      label="Gross PnL"
                      value={`$${trade.gross_pnl?.toFixed(2)}`}
                      valueClass={trade.gross_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}
                    />
                    <InfoRow label="Swap" value={`$${trade.swap?.toFixed(2)}`} valueClass="text-slate-500" />
                    <InfoRow
                      label="MFE"
                      value={trade.mfe_r != null ? `+${trade.mfe_r.toFixed(3)}R` : trade.mfe != null ? `+${trade.mfe.toFixed(5)} price` : 'Awaiting M1'}
                      valueClass="text-emerald-400/70"
                    />
                    <InfoRow
                      label="MAE"
                      value={trade.mae_r != null ? `${trade.mae_r.toFixed(3)}R` : trade.mae != null ? `${trade.mae.toFixed(5)} price` : 'Awaiting M1'}
                      valueClass="text-rose-400/70"
                    />
                    <InfoRow
                      label="Excursion Quality"
                      value={trade.excursion_source === 'verified_m1' ? `Verified M1 · ${Math.round((trade.excursion_coverage  0) * 100)}%` : 'Not verified'}
                      valueClass={trade.excursion_source === 'verified_m1' ? 'text-[var(--c-neutral)]' : 'text-[var(--c-warning)]'}
                    />
                    {trade.magic_number !== null && trade.magic_number !== undefined && (
                      <InfoRow
                        label="Bot ID"
                        value={Number(trade.magic_number) === 0 ? `Manual ${trade.magic_number}` : ` ${trade.magic_number}`}
                        valueClass={Number(trade.magic_number) === 0 ? 'text-amber-600' : 'text-[var(--c-neutral)]'}
                      />
                    )}
                  </div>
                </div>
              </section>

              {/* ── What-If Scenario (Sin Parciales) ── */}
              {trade.planned_tp !== undefined && trade.planned_tp !== null && trade.planned_tp > 0 && (
                <section className="mt-8">
                  <div className="flex items-center gap-2 mb-4">
                    <h3 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest">Escenario &quot;Sin Parciales&quot; (What-If)</h3>
                    <div className="flex-1 divider" style={{ borderColor: 'var(--bg-border)' }} />
                  </div>
                  <div className="rounded-xl p-5 border border-[var(--bg-border)]" style={{ background: 'var(--bg-surface)' }}>
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <InfoRow label="TP Planeado Final" value={trade.planned_tp?.toFixed(5)} valueClass="text-emerald-400" />
                        <InfoRow label="R Máximo Teórico" value={`${trade.planned_max_r?.toFixed(2)}R`} valueClass="text-blue-400" />
                        <InfoRow label="Resultado Simulado" value={
                          trade.what_if_result === 'tp_hit' ? ' TP Alcanzado' :
                          trade.what_if_result === 'sl_hit' ? ' SL Tocado' :
                          trade.what_if_result === 'open' ? ' Sin Tocar' : 'Desconocido'
                        } valueClass={
                          trade.what_if_result === 'tp_hit' ? 'text-emerald-400 font-bold' :
                          trade.what_if_result === 'sl_hit' ? 'text-rose-400 font-bold' : 'text-slate-400'
                        } />
                      </div>
                      <div className="space-y-2 border-l border-[var(--bg-border)] pl-6">
                        <InfoRow label="P&L Simulado (Sin Parciales)" value={
                          trade.what_if_pnl !== undefined && trade.what_if_pnl !== null 
                            ? `${trade.what_if_pnl >= 0 ? '+' : ''}$${trade.what_if_pnl?.toFixed(2)}` 
                            : 'N/A'
                        } valueClass={
                          trade.what_if_pnl && trade.what_if_pnl >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'
                        } />
                        <InfoRow label="R Múltiplo Simulado" value={
                          trade.what_if_r !== undefined && trade.what_if_r !== null 
                            ? `${trade.what_if_r?.toFixed(2)}R` 
                            : 'N/A'
                        } valueClass="text-slate-300" />
                        
                        {trade.what_if_pnl !== undefined && trade.what_if_pnl !== null && (
                          <InfoRow 
                            label="Diferencia (Real vs Plan)" 
                            value={`${(trade.netpnl - trade.what_if_pnl) >= 0 ? '+' : ''}$${(trade.netpnl - trade.what_if_pnl).toFixed(2)}`} 
                            valueClass={(trade.netpnl - trade.what_if_pnl) >= 0 ? 'text-emerald-400 font-medium' : 'text-rose-400 font-medium'} 
                          />
                        )}
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* ── Institutional Micro-Structure ── */}
              <section className="mt-8 mb-4">
                <div className="flex items-center gap-2 mb-4">
                  <h3 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest">Institutional Micro-Structure</h3>
                  <div className="flex-1 divider" style={{ borderColor: 'var(--bg-border)' }} />
                </div>
                
                <div className="rounded-xl p-5 border border-[var(--bg-border)] bg-[var(--bg-surface)]">
                   <div className="grid grid-cols-2 gap-8">
                      <div>
                        <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest mb-3">Time-Weighted Excursion</p>
                        <div className="space-y-4">
                          <div>
                            <div className="flex justify-between mb-1.5">
                              <span className="text-xs text-slate-400 font-medium font-data text-emerald-400/80">TW-MFE (Mean Favorable)</span>
                              <span className="text-xs font-bold text-emerald-400 font-data">{trade.tw_mfe_r != null ? `+${trade.tw_mfe_r.toFixed(3)}R` : 'N/A'}</span>
                            </div>
                            <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                              <motion.div initial={{ width: 0 }} animate={{ width: `${Math.min((trade.tw_mfe_r  0) * 20, 100)}%` }} className="h-full bg-emerald-500/40" />
                            </div>
                          </div>
                          <div>
                            <div className="flex justify-between mb-1.5">
                              <span className="text-xs text-slate-400 font-medium font-data text-rose-400/80">TW-MAE (Mean Adverse)</span>
                              <span className="text-xs font-bold text-rose-400 font-data">{trade.tw_mae_r != null ? `${trade.tw_mae_r.toFixed(3)}R` : 'N/A'}</span>
                            </div>
                            <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                              <motion.div initial={{ width: 0 }} animate={{ width: `${Math.min(Math.abs(trade.tw_mae_r  0) * 20, 100)}%` }} className="h-full bg-rose-500/40" />
                            </div>
                          </div>
                        </div>
                        
                        {trade.r_multiple_adj !== undefined && trade.r_multiple_adj !== null && (
                          <div className="mt-4 pt-3 border-t border-white/5 flex justify-between items-center">
                             <span className="text-[10px] text-slate-500 uppercase tracking-widest">Vol-Adjusted R</span>
                             <span className="text-xs font-bold text-blue-400 font-data">{trade.r_multiple_adj.toFixed(3)}R</span>
                          </div>
                        )}
                      </div>
 
                      <div className="flex flex-col justify-center border-l border-[var(--bg-border)] pl-8">
                         <div className="flex items-center gap-2 mb-2">
                            <Zap className="w-3 h-3 text-amber-500" />
                            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest">Execution Efficiency</p>
                         </div>
                         <div className="flex items-baseline gap-2">
                            <span className="text-3xl font-black text-[var(--text-primary)] font-data">
                               {trade.efficiency != null ? `${(trade.efficiency * 100).toFixed(1)}%` : 'N/A'}
                            </span>
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${ (trade.efficiency  0) > 0.7 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`}>
                               { trade.efficiency == null ? 'UNVERIFIED' : trade.efficiency > 0.7 ? 'PRECISE' : 'SUBOPTIMAL' }
                            </span>
                         </div>
                         <p className="text-[9px] text-slate-600 mt-2 leading-relaxed italic">
                           Measures the percentage of the total favorable excursion captured by the exit algorithm.
                         </p>
                         
                         {trade.execution_slippage_cash !== undefined && trade.execution_slippage_cash !== null && trade.execution_slippage_cash > 0.01 && (
                            <div className="mt-4 pt-3 border-t border-white/5">
                               <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Execution Slippage</p>
                               <p className="font-data text-xs font-bold text-rose-400">
                                  -${trade.execution_slippage_cash.toFixed(2)} ({trade.execution_slippage_r?.toFixed(2)}R)
                               </p>
                               <p className="text-[8px] text-slate-600 mt-0.5">Dinero dejado en la mesa por pánico/salida anticipada.</p>
                            </div>
                         )}
                      </div>
                   </div>
                </div>
              </section>

              {/* ── Qualitative Journal & Mindset (Stagger Effect) ── */}
              {journalData && (journalData.notes_general  journalData.emotional_tags  journalData.notes_pre) && (
                <section className="mt-8">
                  <div className="flex items-center gap-2 mb-4">
                    <h3 className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest">Mindset & Qualitative Journal</h3>
                    <div className="flex-1 divider" style={{ borderColor: 'var(--bg-border)' }} />
                  </div>
                  
                  <motion.div 
                    variants={containerVariants}
                    initial="hidden"
                    animate="show"
                    className="space-y-3"
                  >
                    {/* Emotions */}
                    {journalData.emotional_tags && (
                      <motion.div variants={itemVariants} className="rounded-xl p-4 border border-[var(--bg-border)] bg-[var(--bg-surface)] flex items-center justify-between">
                        <div>
                          <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest mb-1.5">Mental State during execution</p>
                          <div className="flex flex-wrap gap-1.5">
                            {journalData.emotional_tags.split(',').filter(Boolean).map((tag: string) => (
                              <span key={tag} className="px-2.5 py-0.5 rounded-full bg-slate-500/10 text-slate-300 border border-slate-500/20 text-[10px] font-bold">
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>
                        {journalData.emotional_state && (
                          <div className="text-right border-l border-[var(--bg-border)] pl-4 shrink-0">
                            <p className="text-[9px] text-[var(--text-muted)] uppercase tracking-widest">Score</p>
                            <p className="font-data font-black text-xl text-[var(--c-neutral)]">{journalData.emotional_state}/10</p>
                          </div>
                        )}
                      </motion.div>
                    )}

                    {/* Notes grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {[
                        { label: 'Pre-Trade Context', value: journalData.notes_pre },
                        { label: 'During execution notes', value: journalData.notes_during },
                        { label: 'Post-Execution analysis', value: journalData.notes_post },
                        { label: 'AI Review Summary / General notes', value: journalData.notes_general }
                      ].map(({ label, value }) => {
                        if (!value) return null;
                        return (
                          <motion.div 
                            key={label} 
                            variants={itemVariants}
                            className="rounded-xl p-4 border border-[var(--bg-border)] bg-[var(--bg-surface)]"
                          >
                            <p className="text-[9px] text-[var(--text-muted)] uppercase tracking-widest mb-2 font-bold">{label}</p>
                            <p className="text-xs leading-relaxed text-[var(--text-secondary)] font-medium italic">&quot;{value}&quot;</p>
                          </motion.div>
                        )
                      })}
                    </div>
                  </motion.div>
                </section>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
