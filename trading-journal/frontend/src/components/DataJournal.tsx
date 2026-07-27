'use client'
import React, { useMemo } from 'react'
import { ColumnDef } from '@tanstack/react-table'
import { DataTable } from './DataTable'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { motion } from 'framer-motion'
import { BarChart2, Target, Award, Sparkles } from 'lucide-react'
import type { AiIntent } from '@/lib/ai'

function cn(...inputs: Array<string  false  null  undefined>) { return twMerge(clsx(...inputs)) }

type Trade = {
  symbol: string; entrytime: string; direction: 'Buy'  'Sell'; volume: number
  netpnl: number; r_multiple: number; entryprice: number; exitprice: number
  commission: number; magic_number: number  null; mae_r: number  null; mfe_r: number  null
  mae?: number  null; mfe?: number  null; excursion_source?: string  null; excursion_coverage?: number  null
  planned_tp?: number  null
  planned_max_r?: number  null
  what_if_result?: string  null
  what_if_pnl?: number  null
  what_if_r?: number  null
  partials?: string  null
}

interface QuantData {
  e_ratio: number  null
  commission_drag_pct: number
  runs_zscore: number
  serial_independent: boolean
  excursion_verified_count?: number
  excursion_coverage?: number
}
interface Props { data: Trade[]; quant?: QuantData; onAskAi?: (intent: AiIntent) => void }

const columns: ColumnDef<Trade>[] = [
  {
    accessorKey: 'symbol', header: 'Símbolo',
    cell: ({ row }) => {
      const symbol = row.getValue('symbol') as string
      const partialsRaw = row.original.partials
      let hasPartials = false
      try {
        if (partialsRaw) {
          const parsed = JSON.parse(partialsRaw)
          hasPartials = Array.isArray(parsed) && parsed.length > 0
        }
      } catch {}

      return (
        <div className="flex items-center gap-2">
          <span className="text-[var(--text-primary)] font-bold">{symbol}</span>
          {hasPartials && (
            <span className="flex items-center justify-center w-3 h-3 rounded-full bg-blue-500/20 text-blue-400 text-[8px] font-black border border-blue-500/30">
              P
            </span>
          )}
        </div>
      )
    }
  },
  {
    accessorKey: 'entrytime', header: 'Hora',
    cell: ({ row }) => {
      const date = new Date(row.getValue('entrytime'))
      return <span className="text-[var(--text-muted)] text-xs font-mono">{date.toLocaleString('es-ES', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
    }
  },
  {
    accessorKey: 'direction', header: 'Lado',
    cell: ({ row }) => {
      const sideRaw = row.getValue('direction') as string
      const side = sideRaw === 'Buy' ? 'Compra' : 'Venta'
      return (
        <span className={cn("px-2 py-1 rounded text-[10px] uppercase font-black",
          sideRaw === 'Buy' ? "bg-blue-500/20 text-blue-400" : "bg-orange-500/20 text-orange-400"
        )}>{side}</span>
      )
    }
  },
  {
    accessorKey: 'volume', header: 'Lotes',
    cell: ({ row }) => <span className="font-mono text-xs">{Number(row.getValue('volume')).toFixed(2)}</span>
  },
  {
    accessorKey: 'netpnl', header: 'PnL ($)',
    cell: ({ row }) => {
      const amount = parseFloat(row.getValue('netpnl'))
      return (
        <span className={cn("font-bold", amount >= 0 ? "text-emerald-400" : "text-rose-400")}>
          {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)}
        </span>
      )
    }
  },
  {
    accessorKey: 'r_multiple', header: 'R',
    cell: ({ row }) => {
      const r = parseFloat(row.getValue('r_multiple'))
      if (isNaN(r)) return <span className="text-[var(--text-muted)] text-xs">N/A</span>
      return (
        <span className={cn("px-2 py-0.5 rounded font-mono text-xs whitespace-nowrap",
          r >= 2 ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" :
          r <= -1 ? "bg-rose-500/20 text-rose-400" : "bg-[var(--bg-hover)] text-[var(--text-secondary)]"
        )}>{r.toFixed(2)}R</span>
      )
    }
  },
  {
    accessorKey: 'what_if_pnl', header: 'PnL What-If ($)',
    cell: ({ row }) => {
      const val = row.original.what_if_pnl
      if (val === undefined  val === null) return <span className="text-slate-700 text-xs">-</span>
      const amount = Number(val)
      const outcome = row.original.what_if_result
      const label = outcome === 'tp_hit' ? ' TP' : outcome === 'sl_hit' ? ' SL' : ' Open'
      return (
        <div className="flex flex-col gap-0.5">
          <span className={cn("font-bold text-xs font-mono", amount >= 0 ? "text-emerald-400/80" : "text-rose-400/80")}>
            {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)}
          </span>
          <span className="text-[8px] text-slate-500 font-black tracking-widest">{label}</span>
        </div>
      )
    }
  },
  {
    accessorKey: 'mfe_r', header: 'MFE',
    cell: ({ row }) => {
      const val = row.getValue('mfe_r') as number  null
      if (row.original.excursion_source !== 'verified_m1') return <span className="text-[var(--c-warning)] text-[10px]">UNVERIFIED</span>
      if (val === null  val === undefined) return <span className="text-[var(--text-muted)] text-xs">PRICE ONLY</span>
      return <span className="text-emerald-500/70 text-xs font-mono">{Number(val).toFixed(2)}R</span>
    }
  },
  {
    accessorKey: 'mae_r', header: 'MAE',
    cell: ({ row }) => {
      const val = row.getValue('mae_r') as number  null
      if (row.original.excursion_source !== 'verified_m1') return <span className="text-[var(--c-warning)] text-[10px]">UNVERIFIED</span>
      if (val === null  val === undefined) return <span className="text-[var(--text-muted)] text-xs">PRICE ONLY</span>
      return <span className="text-rose-500/70 text-xs font-mono">{Number(val).toFixed(2)}R</span>
    }
  },
  {
    accessorKey: 'commission', header: 'Com.',
    cell: ({ row }) => {
      const c = parseFloat(row.getValue('commission'))
      return <span className="text-[var(--text-muted)] text-xs font-mono">{c.toFixed(2)}</span>
    }
  },
  {
    accessorKey: 'magic_number', header: 'Bot ID',
    cell: ({ row }) => {
      const raw = row.getValue('magic_number')
      if (raw === null  raw === undefined  raw === '') return <span className="text-[var(--text-muted)]">-</span>

      const magic = Number(raw)
      if (!Number.isFinite(magic)) return <span className="text-[var(--text-muted)]">-</span>

      if (magic === 0) {
        return <span className="text-amber-600 bg-amber-500/10 px-2 py-1 rounded text-[10px] font-mono border border-amber-500/20">Manual 0</span>
      }

      return <span className="text-[var(--text-secondary)] bg-[var(--bg-hover)] px-2 py-1 rounded text-[10px] font-mono border border-[var(--bg-border-strong)]"> {magic}</span>
    }
  }
]

function MiniStat({ label, value, sub, color, trend }: { label: string; value: string; sub?: string; color?: string; trend?: 'up'  'down'  'neutral' }) {
  return (
    <div className="glass-card-heavy p-4 hover:border-[var(--bg-border-strong)] transition-all group relative overflow-hidden">
      <div className="absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity">
        <BarChart2 className="w-8 h-8" />
      </div>
      <p className="text-[10px] text-slate-500 uppercase tracking-[0.2em] mb-2 font-bold">{label}</p>
      <div className="flex items-end gap-2">
        <p className={cn("text-2xl font-black font-data tracking-tighter", color  'text-[var(--text-primary)]')}>
          {value}
        </p>
        {trend && (
          <span className={cn(
            "text-[10px] font-black px-1.5 py-0.5 rounded mb-1",
            trend === 'up' ? "bg-emerald-500/20 text-emerald-400" :
            trend === 'down' ? "bg-rose-500/20 text-rose-400" : "bg-slate-500/20 text-slate-400"
          )}>
            {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
          </span>
        )}
      </div>
      {sub && <p className="text-[10px] text-slate-500 mt-1 font-medium italic opacity-70">{sub}</p>}
    </div>
  )
}

export default function DataJournal({ data, quant, onAskAi }: Props) {
  const wins = data.filter(t => t.netpnl > 0)
  const losses = data.filter(t => t.netpnl < 0)
  const grossPnL = data.reduce((s, t) => s + t.netpnl, 0)
  const totalComm = data.reduce((s, t) => s + (t.commission  0), 0)
  const avgR = useMemo(() => {
    const rs = data.map(t => t.r_multiple).filter(r => r != null && isFinite(r))
    return rs.length > 0 ? rs.reduce((a, b) => a + b, 0) / rs.length : 0
  }, [data])

  const streaks = useMemo(() => {
    let maxWin = 0, maxLoss = 0, curW = 0, curL = 0
    data.forEach(t => {
      if (t.netpnl > 0) { curW++; curL = 0; maxWin = Math.max(maxWin, curW) }
      else if (t.netpnl < 0) { curL++; curW = 0; maxLoss = Math.max(maxLoss, curL) }
      else { curW = 0; curL = 0 }
    })
    return { maxWin, maxLoss }
  }, [data])

  const diaryPrompt =
    `Redacta una entrada automatica de diario de trading con tono profesional. ` +
    `Resumen: ${data.length} operaciones, wins ${wins.length}, losses ${losses.length}, net PnL $${grossPnL.toFixed(2)}, ` +
    `comisiones $${Math.abs(totalComm).toFixed(2)}, avg R ${avgR.toFixed(3)}R, max win streak ${streaks.maxWin}, max loss streak ${streaks.maxLoss}. ` +
    `Explica disciplina, costes, sesgo de ejecucion y una mejora concreta para la siguiente sesion.`

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      {/* Summary Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <MiniStat label="Total Trades" value={String(data.length)} trend="neutral" />
        <MiniStat label="Victorias / Derrotas" value={`${wins.length} / ${losses.length}`}
          color={wins.length > losses.length ? 'text-emerald-400 text-glow-green' : 'text-rose-400 text-glow-red'}
          trend={wins.length > losses.length ? 'up' : 'down'} />
        <MiniStat label="PnL Neto" value={`$${grossPnL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          color={grossPnL >= 0 ? 'text-emerald-400 text-glow-green' : 'text-rose-400 text-glow-red'}
          trend={grossPnL >= 0 ? 'up' : 'down'} />
        <MiniStat label="Promedio R" value={`${avgR.toFixed(3)}R`}
          color={avgR >= 0 ? 'text-blue-400' : 'text-rose-400'}
          sub="Expectativa por trade"
          trend={avgR >= 0.2 ? 'up' : 'neutral'} />
        <MiniStat label="Racha Ganadora Máx" value={`${streaks.maxWin}`} color="text-emerald-400" trend="up" />
        <MiniStat label="Racha Perdedora Máx" value={`${streaks.maxLoss}`} color="text-rose-400" trend="down" />
      </div>

      {/* Serial Independence Banner */}
      {quant && (
        <div className={cn(
          "flex items-center justify-between px-5 py-3 rounded-xl border text-sm",
          quant.serial_independent
            ? "bg-emerald-500/5 border-emerald-500/20"
            : "bg-yellow-500/5 border-yellow-500/20"
        )}>
          <div className="flex items-center gap-3">
            <BarChart2 className={`w-4 h-4 ${quant.serial_independent ? 'text-emerald-400' : 'text-yellow-400'}`} />
            <span className="font-bold text-slate-300">Análisis de Independencia Serial</span>
            <span className={`text-[10px] uppercase font-black px-2 py-0.5 rounded ${quant.serial_independent ? 'bg-emerald-500/20 text-emerald-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
              {quant.serial_independent ? 'Trades Independientes' : 'Agrupamiento Detectado'}
            </span>
          </div>
          <span className="text-slate-500 font-mono text-xs">
            Z-Score = {(quant.runs_zscore  0).toFixed(3)} &nbsp;  &nbsp; Coste de Comisiones: {((quant.commission_drag_pct  0) * 100).toFixed(3)}%
          </span>
        </div>
      )}

      {/* Execution Quality Bar */}
      {quant && (
        <div className="glass-card p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-bold text-[var(--text-primary)]">MAE/MFE Data Quality</p>
            <p className="mt-1 text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Only verified M1 paths contribute to E-Ratio</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="h-2 w-36 overflow-hidden rounded-full bg-[var(--bg-void)]">
              <div className="h-full rounded-full bg-[var(--c-neutral)]" style={{ width: `${Math.min(100, (quant.excursion_coverage  0) * 100)}%` }} />
            </div>
            <span className="font-data text-sm font-black text-[var(--text-primary)]">{((quant.excursion_coverage  0) * 100).toFixed(1)}%</span>
            <span className="text-[10px] text-[var(--text-muted)]">{quant.excursion_verified_count  0} verified</span>
          </div>
        </div>
      )}

      {quant?.e_ratio != null && (
        <div className="glass-card p-4 flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-bold text-[var(--text-primary)]">Edge (E-Ratio)</span>
          </div>
          <div className="flex-1 bg-white/5 rounded-full h-2 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(quant.e_ratio * 50, 100)}%` }}
              className={`h-full rounded-full ${quant.e_ratio > 1 ? 'bg-emerald-500' : 'bg-rose-500'}`}
            />
          </div>
          <span className={`font-mono font-bold text-lg ${quant.e_ratio > 1 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {quant.e_ratio.toFixed(3)}
          </span>
          <span className="text-[10px] text-slate-500">{quant.e_ratio > 1 ? 'Valid Edge ' : 'Below Threshold '}</span>
        </div>
      )}

      {/* Main Table */}
      <div className="glass-card p-0 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--bg-border)]">
          <h2 className="text-base font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-2">
            <Award className="w-4 h-4 text-blue-400" /> Registro de Ejecución
          </h2>
          <div className="flex items-center gap-3">
            {onAskAi && (
              <button
                type="button"
                onClick={() => onAskAi({ focus: 'Diario de datos', prompt: diaryPrompt })}
                className="inline-flex items-center gap-1 rounded-full border border-[rgba(139,92,246,0.25)] bg-[rgba(75,163,199,0.12)] px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-[var(--c-info)] transition-colors hover:bg-[rgba(75,163,199,0.18)]"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Diario IA
              </button>
            )}
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest">{data.length} Trades · Comisión Neta: ${Math.abs(totalComm).toFixed(2)}</p>
          </div>
        </div>
        <div className="p-6 pt-4">
          <DataTable columns={columns} data={data} searchKey="symbol" />
        </div>
      </div>
    </motion.div>
  )
}
