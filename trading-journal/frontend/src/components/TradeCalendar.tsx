'use client'

import React, { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import ReactECharts from 'echarts-for-react'
import { Thermometer, Waves, Clock, Calendar as CalendarIcon, ChevronLeft, ChevronRight, BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Trade {
  symbol: string
  entrytime: string
  direction: string
  netpnl: number
  r_multiple: number
  volume: number
  position_id?: number
}

interface EquityPoint {
  date: string
  time?: string
  equity: number
  drawdown?: number
  dd: number
  pnl: number
}

interface TemporalDynamicsProps {
  trades: Trade[]
  equityCurve: EquityPoint[]
  onTradeClick?: (trade: Trade) => void
}

interface CalendarDayStats {
  pnl: number
  count: number
  r: number
}

interface CalendarDayCell {
  day: number
  date: string
  stats: CalendarDayStats  null
}

const safeParseDate = (v: unknown) => {
  if (!v) return null
  try {
    const d = typeof v === 'number' ? new Date(v > 1e12 ? v : v * 1000) : new Date(String(v))
    if (isNaN(d.getTime())) return null
    // Evitar fechas extremas que rompen toISOString
    const year = d.getFullYear()
    if (year < 1900  year > 2100) return null
    return d
  } catch {
    return null
  }
}

// ─── Module A: TradeZella Performance Calendar ─────────────────────────────
function PerformanceCalendar({ trades }: { trades: Trade[] }) {
  const [currentDate, setCurrentDate] = useState(new Date())

  const calendarData = useMemo(() => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()
    
    // Days in month
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    
    // Group trades by date
    const dailyStats: Record<string, CalendarDayStats> = {}
    trades.forEach(t => {
      const d = safeParseDate(t.entrytime)
      if (!d  isNaN(d.getTime())) return
      const dateStr = d.toISOString().split('T')[0]
      if (!dailyStats[dateStr]) dailyStats[dateStr] = { pnl: 0, count: 0, r: 0 }
      dailyStats[dateStr].pnl += t.netpnl
      dailyStats[dateStr].count += 1
      dailyStats[dateStr].r += t.r_multiple
    })

    const weeks: Array<{ days: Array<CalendarDayCell  null>; summary: { pnl: number; count: number } }> = []
    let currentWeek: Array<CalendarDayCell  null> = Array(7).fill(null)

    // Fill days
    for (let i = 1; i <= daysInMonth; i++) {
      const dayDate = new Date(year, month, i)
      const dayOfWeek = dayDate.getDay()
      const d = safeParseDate(dayDate)
      if (!d) continue
      const dateKey = d.toISOString().split('T')[0]
      
      currentWeek[dayOfWeek] = {
        day: i,
        date: dateKey,
        stats: dailyStats[dateKey]  null
      }

      if (dayOfWeek === 6  i === daysInMonth) {
        // Calculate weekly total
        const weekPnl = currentWeek.reduce((acc, d) => acc + (d?.stats?.pnl  0), 0)
        const weekTrades = currentWeek.reduce((acc, d) => acc + (d?.stats?.count  0), 0)
        
        weeks.push({
          days: [...currentWeek],
          summary: { pnl: weekPnl, count: weekTrades }
        })
        currentWeek = Array(7).fill(null)
      }
    }

    return weeks
  }, [trades, currentDate])

  const nextMonth = () => setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1))
  const prevMonth = () => setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1))

  const monthName = currentDate.toLocaleString('es-ES', { month: 'long', year: 'numeric' })
  const dayNames = ['Dom', 'Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab']


  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <CalendarIcon className="w-4 h-4 text-[#5C6BC0]" />
          <h3 className="text-sm font-bold text-[var(--text-primary)]">{monthName}</h3>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={prevMonth} className="p-1 hover:bg-white/[0.05] rounded-md transition-colors">
            <ChevronLeft className="w-4 h-4 text-[var(--text-secondary)]" />
          </button>
          <button onClick={nextMonth} className="p-1 hover:bg-white/[0.05] rounded-md transition-colors">
            <ChevronRight className="w-4 h-4 text-[var(--text-secondary)]" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-8 gap-2">
        {/* Header */}
        {dayNames.map(d => (
          <div key={d} className="text-center text-[10px] uppercase font-bold text-[var(--text-muted)] tracking-widest pb-2">
            {d}
          </div>
        ))}
        <div className="text-center text-[10px] uppercase font-bold text-[#5C6BC0] tracking-widest pb-2">Semana</div>

        {/* Grid */}
        {calendarData?.map((week, wi) => (
          <React.Fragment key={wi}>
            {week.days.map((day, di) => (
              <div 
                key={di} 
                className={cn(
                  "min-h-[80px] rounded-lg border border-[var(--bg-border)] p-2 flex flex-col items-center justify-between transition-all",
                  !day && "opacity-20",
                  (day?.stats?.pnl ?? 0) > 0 && "bg-[var(--c-positive-dim)] border-[rgba(16,185,129,0.2)]",
                  (day?.stats?.pnl ?? 0) < 0 && "bg-[var(--c-negative-dim)] border-[rgba(244,63,94,0.2)]",
                  day && !day.stats && "bg-black/5"
                )}
              >
                <span className="text-[10px] font-bold text-[var(--text-muted)] self-start">{day?.day  ''}</span>
                {day?.stats ? (
                  <div className="flex flex-col items-center gap-0.5">
                    <span className={cn(
                      "text-xs font-black font-data",
                      day.stats.pnl > 0 ? "text-[var(--c-positive)]" : "text-[var(--c-negative)]"
                    )}>
                      {day.stats.pnl > 0 ? '+' : ''}${Math.abs(day.stats.pnl).toFixed(0)}
                    </span>
                    <div className="flex items-center gap-1.5 mt-1">
                      <span className="text-[8px] px-1 rounded font-data" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>
                        {day.stats.count}T
                      </span>
                      <span className={cn(
                        "text-[8px] font-bold font-data",
                        day.stats.r > 0 ? "text-[var(--c-positive)]" : "text-[var(--c-negative)]"
                      )}>
                        {day.stats.r.toFixed(1)}R
                      </span>
                    </div>
                  </div>
                ) : null}
              </div>
            ))}
            {/* Weekly Summary */}
            <div className="bg-[#5C6BC0]/5 rounded-lg border border-[#5C6BC0]/10 p-2 flex flex-col items-center justify-center gap-1">
              <span className={cn(
                "text-[10px] font-black font-data",
                week.summary.pnl >= 0 ? "text-[var(--c-positive)]" : "text-[var(--c-negative)]"
              )}>
                {week.summary.pnl >= 0 ? '+' : ''}${Math.abs(week.summary.pnl).toLocaleString()}
              </span>
              <span className="text-[8px] text-[var(--text-muted)] uppercase tracking-tighter">
                {week.summary.count} Operaciones
              </span>
            </div>
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

// ─── Module B: PnL Heatmap (GitHub Contribution Style) ─────────────────────
function PnLHeatmap({ trades }: { trades: Trade[] }) {
  const { matrix, weeks, maxAbsPnl } = useMemo(() => {
    const dailyPnl: Record<string, number> = {}
    trades.forEach(t => {
      const d = safeParseDate(t.entrytime)
      if (!d  isNaN(d.getTime())) return
      const dateStr = d.toISOString().split('T')[0]
      dailyPnl[dateStr] = (dailyPnl[dateStr]  0) + t.netpnl
    })

    const today = new Date()
    const weeks: string[][] = []
    for (let w = 11; w >= 0; w--) { // Reduced to 12 weeks for better spacing
      const weekDays: string[] = []
      for (let d = 0; d < 5; d++) {
        const date = new Date(today)
        date.setDate(today.getDate() - (w * 7) + d - today.getDay() + 1)
        weekDays.push(date.toISOString().split('T')[0])
      }
      weeks.push(weekDays)
    }

    const maxAbsPnl = Math.max(1, ...Object.values(dailyPnl).map(Math.abs))
    return { matrix: dailyPnl, weeks, maxAbsPnl }
  }, [trades])

  const getCellColor = (pnl: number  undefined) => {
    if (pnl === undefined) return 'var(--bg-surface)'
    if (pnl === 0) return 'var(--bg-surface)'
    const intensity = Math.min(Math.abs(pnl) / maxAbsPnl, 1)
    return pnl > 0
      ? `rgba(46, 139, 87, ${0.15 + intensity * 0.75})`
      : `rgba(211, 47, 47, ${0.15 + intensity * 0.75})`
  }

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-4">
        <Thermometer className="w-3.5 h-3.5 text-[var(--c-accent)]" />
        <h3 className="font-bold text-sm text-[var(--text-primary)]">Mapa de calor</h3>
      </div>
      <div className="flex gap-1.5 overflow-x-auto pb-2">
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-1.5">
            {week.map((date) => (
              <div
                key={date}
                className="w-4 h-4 rounded-[2px] cursor-default transition-all hover:scale-110"
                style={{
                  backgroundColor: getCellColor(matrix[date]),
                  border: '1px solid var(--bg-border)',
                  outline: matrix[date] !== undefined ? '1px solid rgba(0,0,0,0.08)' : 'none',
                }}
                title={matrix[date] !== undefined ? `${date}: $${matrix[date].toFixed(2)}` : date}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Module C: Underwater Drawdown Plot ────────────────────────────────────
function UnderwaterPlot({ equityCurve }: { equityCurve: EquityPoint[] }) {
  const chartData = useMemo(() => {
    return equityCurve.map(pt => {
      const raw = pt.date  pt.time
      const d = safeParseDate(raw)
      const validDate = d && !isNaN(d.getTime())
      const months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
      const label = validDate ? `${d.getDate()} ${months[d.getMonth()]}` : (raw  '')
      return [label, ((pt.drawdown ?? pt.dd ?? 0) * 100)]
    })
  }, [equityCurve])

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'var(--bg-elevated)',
      borderColor: 'var(--bg-border)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)', fontSize: 10 },
      formatter: (params: Array<{ value: [string, number] }>) => `
        <div style="font-family:monospace">
          <p style="color:var(--text-muted); font-size:9px; margin:0">DRAWDOWN</p>
          <p style="color:var(--c-negative); font-size:14px; font-weight:800; margin:2px 0">${(params[0]?.value?.[1] ?? 0).toFixed(2)}%</p>
        </div>
      `
    },
    grid: { top: '10%', left: '3%', right: '3%', bottom: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'var(--text-muted)', fontSize: 8, fontFamily: 'monospace' }
    },
    yAxis: {
      type: 'value',
      max: 0,
      splitLine: { lineStyle: { color: 'var(--bg-border)', type: 'dashed' } },
      axisLabel: { color: 'var(--text-muted)', fontSize: 8, fontFamily: 'monospace', formatter: '{value}%' }
    },
    series: [{
      type: 'line',
      step: 'end',
      symbol: 'none',
      lineStyle: { width: 1.5, color: 'var(--c-negative)' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(211, 47, 47, 0.2)' }, { offset: 1, color: 'rgba(211, 47, 47, 0)' }]
        }
      },
      data: chartData
    }]
  }

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Waves className="w-3.5 h-3.5 text-[var(--c-negative)]" />
        <h3 className="font-bold text-sm text-[var(--text-primary)]">Curva de Drawdown</h3>
      </div>
      <div className="h-[180px]">
        <ReactECharts option={option} style={{ height: '100%' }} opts={{ renderer: 'svg' }} />
      </div>
    </div>
  )
}

// ─── Module D: Session & Radar Score ───────────────────────────────────────
function QuantitativeRadar({ trades }: { trades: Trade[] }) {
  const stats = useMemo(() => {
    if (trades.length === 0) return [0, 0, 0, 0, 0]
    const wins = trades.filter(t => t.netpnl > 0).length
    const winRate = wins / trades.length
    const avgWin = trades.filter(t => t.netpnl > 0).reduce((acc, t) => acc + t.netpnl, 0) / (wins  1)
    const avgLoss = Math.abs(trades.filter(t => t.netpnl <= 0).reduce((acc, t) => acc + t.netpnl, 0) / (trades.length - wins  1))
    const pf = avgWin / (avgLoss  1)
    const expectancy = trades.reduce((acc, t) => acc + t.r_multiple, 0) / trades.length
    
    // Normalize for radar (0-100)
    return [
      Math.min(winRate * 100 * 1.5, 100), // WinRate (61% goal)
      Math.min(pf * 30, 100),            // PF (3.0 goal)
      Math.min(expectancy * 100, 100),   // Expectancy (1R goal)
      Math.min(trades.length * 2, 100),  // Sample Size (50 goal)
      75                                 // Sharpness (static placeholder)
    ]
  }, [trades])

  const option = {
    backgroundColor: 'transparent',
    radar: {
      indicator: [
        { name: 'Acierto', max: 100 },
        { name: 'Profit Factor', max: 100 },
        { name: 'Expectativa', max: 100 },
        { name: 'Muestra', max: 100 },
        { name: 'Consistency', max: 100 }
      ],
      splitNumber: 4,
      axisName: { color: 'var(--text-muted)', fontSize: 8, textTransform: 'uppercase' },
      splitLine: { lineStyle: { color: 'var(--chart-gridline)' } },
      splitArea: { areaStyle: { color: ['transparent'] } }
    },
    series: [{
      type: 'radar',
      symbol: 'none',
      data: [{
        value: stats,
        name: 'Score Cuant',
        areaStyle: { color: 'rgba(124, 111, 212, 0.1)' },
        lineStyle: { color: 'var(--c-accent)', width: 1.5 }
      }]
    }]
  }

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 className="w-3.5 h-3.5 text-[var(--c-accent)]" />
        <h3 className="font-bold text-sm text-[var(--text-primary)]">Matriz de puntuacion</h3>
      </div>
      <div className="h-[180px]">
        <ReactECharts option={option} style={{ height: '100%' }} opts={{ renderer: 'svg' }} />
      </div>
    </div>
  )
}

function SessionDistribution({ trades }: { trades: Trade[] }) {
  const hourlyData = useMemo(() => {
    const hours: Record<number, { pnl: number; count: number }> = {}
    for (let h = 0; h < 24; h++) hours[h] = { pnl: 0, count: 0 }
    trades.forEach(t => {
      const d = safeParseDate(t.entrytime)
      if (!d) return
      const h = d.getHours()
      hours[h].pnl += t.netpnl
      hours[h].count += 1
    })
    return Object.entries(hours).map(([h, d]) => ({
      hour: parseInt(h),
      avgPnl: d.count > 0 ? d.pnl / d.count : 0
    }))
  }, [trades])

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'var(--bg-elevated)',
      borderColor: 'var(--bg-border)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)', fontSize: 10 }
    },
    grid: { top: '10%', left: '3%', right: '3%', bottom: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: hourlyData.map(h => `${String(h.hour).padStart(2, '0')}h`),
      axisLabel: { color: 'var(--text-muted)', fontSize: 7, fontFamily: 'monospace', interval: 1 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'var(--bg-border)', type: 'dashed' } },
      axisLabel: { color: 'var(--text-muted)', fontSize: 8, fontFamily: 'monospace' }
    },
    series: [{
      type: 'bar',
      barWidth: '60%',
      data: hourlyData.map(h => ({
        value: h.avgPnl,
        itemStyle: {
          color: h.avgPnl >= 0 ? 'var(--c-positive)' : 'var(--c-negative)',
          borderRadius: 2
        }
      }))
    }]
  }

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-3.5 h-3.5 text-[var(--c-warning)]" />
        <h3 className="font-bold text-sm text-[var(--text-primary)]">Ventaja por sesion</h3>
      </div>
      <div className="h-[180px]">
        <ReactECharts option={option} style={{ height: '100%' }} opts={{ renderer: 'svg' }} />
      </div>
    </div>
  )
}

export default function TemporalDynamics({ trades, equityCurve }: TemporalDynamicsProps) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <PerformanceCalendar trades={trades} />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <PnLHeatmap trades={trades} />
        <SessionDistribution trades={trades} />
        <QuantitativeRadar trades={trades} />
        <UnderwaterPlot equityCurve={equityCurve} />
      </div>
    </motion.div>
  )
}
