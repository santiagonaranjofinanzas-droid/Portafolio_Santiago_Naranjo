'use client'
import ReactEChartsCore from 'echarts-for-react'
import { useState, useMemo, memo } from 'react'
import { clsx } from 'clsx'

type Point = { date?: string; equity?: number; drawdown?: number; [k: string]: unknown }
type Props = { data: Point[] }

const periods = [
  { label: '1W', days: 7 },
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: 'ALL', days: 0 },
] as const

const EquityChart = memo(function EquityChart({ data }: Props) {
  const [period, setPeriod] = useState('ALL')

  const filtered = useMemo(() => {
    if (!data?.length) return []
    const sel = periods.find(p => p.label === period)
    if (!sel  sel.days === 0) return data
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - sel.days)
    return data.filter(p => {
      if (!p.date) return true
      return new Date(p.date) >= cutoff
    })
  }, [data, period])

  const fmtDateLabel = (iso: string): string => {
    if (!iso) return ''
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    const months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    return `${d.getDate()} ${months[d.getMonth()]}`
  }

  const fmtDateFull = (iso: string): string => {
    if (!iso) return ''
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    const months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`
  }

  const option = useMemo(() => {
    const dateLabels = filtered.map(p => fmtDateLabel(p.date ?? ''))
    const dateFullLabels = filtered.map(p => fmtDateFull(p.date ?? ''))
    const equityVals = filtered.map(p => Number(p.equity ?? 0))
    const ddVals = filtered.map(p => Number(p.drawdown ?? 0) * 100)
    const finiteEquity = equityVals.filter(Number.isFinite)
    const equityMin = finiteEquity.length ? Math.min(...finiteEquity) : 0
    const equityMax = finiteEquity.length ? Math.max(...finiteEquity) : 0
    const equityRange = Math.max(equityMax - equityMin, 0)
    const equityPadding = Math.max(equityRange * 0.15, Math.abs(equityMax) * 0.005, 1)
    const equityAxisMin = Math.max(0, equityMin - equityPadding)
    const equityAxisMax = equityMax + equityPadding

    const cs = getComputedStyle(document.documentElement)
    const neutral = cs.getPropertyValue('--c-neutral').trim()  '#3b82f6'
    const negative = cs.getPropertyValue('--c-negative').trim()  '#ef4444'
    const grid = cs.getPropertyValue('--chart-gridline').trim()  'rgba(148,163,184,0.06)'
    const textMuted = cs.getPropertyValue('--text-muted').trim()  '#64748b'

    return {
      animation: true,
      animationDuration: 600,
      grid: { top: 30, right: 60, bottom: 30, left: 60, containLabel: false },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(17,24,39,0.95)',
        borderColor: 'rgba(148,163,184,0.1)',
        textStyle: { color: '#f1f5f9', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' },
        formatter: (params: Array<{seriesName:string;value:number;dataIndex:number;axisValue:string}>) => {
          const idx = params[0]?.dataIndex ?? 0
          const fullDate = dateFullLabels[idx]  params[0]?.axisValue  ''
          let html = `<div style="font-size:10px;color:#94a3b8;margin-bottom:4px">${fullDate}</div>`
          for (const p of params) {
            const color = p.seriesName === 'Equity' ? neutral : negative
            const val = p.seriesName === 'Drawdown' ? `${p.value.toFixed(2)}%` : `$${p.value.toLocaleString(undefined,{minimumFractionDigits:2})}`
            html += `<div style="display:flex;justify-content:space-between;gap:16px"><span style="color:${color}">${p.seriesName}</span><span style="font-weight:600">${val}</span></div>`
          }
          return html
        }
      },
      xAxis: { type: 'category', data: dateLabels, axisLine: { lineStyle: { color: grid } }, axisLabel: { color: textMuted, fontSize: 10, rotate: filtered.length > 30 ? 45 : 0 }, splitLine: { show: false } },
      yAxis: [
        {
          type: 'value',
          position: 'left',
          scale: true,
          min: equityAxisMin,
          max: equityAxisMax,
          axisLine: { show: false },
          axisLabel: {
            color: textMuted,
            fontSize: 10,
            formatter: (value: number) => `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
          },
          splitLine: { lineStyle: { color: grid } },
        },
        { type: 'value', position: 'right', axisLine: { show: false }, axisLabel: { color: textMuted, fontSize: 10, formatter: '{value}%' }, splitLine: { show: false } },
      ],
      series: [
        {
          name: 'Equity', type: 'line', data: equityVals, yAxisIndex: 0,
          smooth: 0.3, symbol: 'none', lineStyle: { width: 2, color: neutral },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: neutral + '30' }, { offset: 1, color: neutral + '05' }] } },
        },
        {
          name: 'Drawdown', type: 'line', data: ddVals, yAxisIndex: 1,
          smooth: 0.3, symbol: 'none', lineStyle: { width: 1.5, color: negative + '80' },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: negative + '20' }, { offset: 1, color: negative + '05' }] } },
        },
      ],
    }
  }, [filtered])

  if (!data?.length) return <div className="chart-container flex items-center justify-center" style={{color:'var(--text-ghost)'}}>No equity data</div>

  return (
    <div>
      <div className="flex justify-end px-4 pb-2">
        <div className="period-tabs">
          {periods.map(p => (
            <button key={p.label} className={clsx('period-tab', period === p.label && 'active')} onClick={() => setPeriod(p.label)}>{p.label}</button>
          ))}
        </div>
      </div>
      <ReactEChartsCore option={option} style={{ height: 340 }} notMerge lazyUpdate opts={{ renderer: 'svg' }} />
    </div>
  )
})

export default EquityChart;
