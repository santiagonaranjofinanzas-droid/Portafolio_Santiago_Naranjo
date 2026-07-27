'use client'

import React, { useMemo, memo } from 'react'
import ReactECharts from 'echarts-for-react'

interface M1Rate {
  time: string
  open: number
  high: number
  low: number
  close: number
}

interface TradeM1ChartProps {
  data: M1Rate[]
  trade: {
    direction: 'Buy'  'Sell'  string
    entryprice: number
    exitprice: number
    entrytime: string
    exittime: string
    sl: number
    risk_price?: number  null
    r_multiple: number
  }
}

const TradeM1Chart = memo(function TradeM1Chart({ data, trade }: TradeM1ChartProps) {
  const seriesData = useMemo(() => (Array.isArray(data) ? data : []), [data])
  const isBuy = trade.direction === 'Buy'

  // ─── Compute REAL MFE & MAE from M1 candles ───────────────────────────
  const { mfePrice, maePrice, mfePct, maePct } = useMemo(() => {
    const entry = trade.entryprice
    if (!entry  !seriesData.length) return { mfePrice: null, maePrice: null, mfePct: null, maePct: null }

    const parseUTC = (str: string) => {
      if (!str) return 0
      const clean = str.replace(' ', 'T')
      return new Date(clean.endsWith('Z') ? clean : clean + 'Z').getTime()
    }

    const entryTime = parseUTC(trade.entrytime)
    const exitTime = parseUTC(trade.exittime)

    let bestExcursion = isBuy ? -Infinity : Infinity  // Best price reached (MFE)
    let worstExcursion = isBuy ? Infinity : -Infinity  // Worst price reached (MAE)
    let count = 0

    seriesData.forEach(bar => {
      const barTime = parseUTC(bar.time)
      const barEndTime = barTime + 60_000
      // Include any M1 candle that overlaps the trade, including sub-minute trades.
      if (barTime <= exitTime && barEndTime > entryTime) {
        count++
        if (isBuy) {
          // For Buy: MFE = highest high, MAE = lowest low
          if (bar.high > bestExcursion) bestExcursion = bar.high
          if (bar.low < worstExcursion) worstExcursion = bar.low
        } else {
          // For Sell: MFE = lowest low, MAE = highest high
          if (bar.low < bestExcursion) bestExcursion = bar.low
          if (bar.high > worstExcursion) worstExcursion = bar.high
        }
      }
    })

    if (count === 0) {
      return { mfePrice: null, maePrice: null, mfePct: null, maePct: null }
    }

    const riskPrice = trade.risk_price  Math.abs(entry - trade.sl)
    const hasRiskBasis = Boolean(trade.sl > 0 && riskPrice > 0)

    const mfePriceFinal = bestExcursion === -Infinity  bestExcursion === Infinity ? null : bestExcursion
    const maePriceFinal = worstExcursion === Infinity  worstExcursion === -Infinity ? null : worstExcursion

    const mfePctCalc = mfePriceFinal !== null && hasRiskBasis
      ? isBuy ? (mfePriceFinal - entry) / riskPrice : (entry - mfePriceFinal) / riskPrice
      : null
    const maePctCalc = maePriceFinal !== null && hasRiskBasis
      ? isBuy ? (entry - maePriceFinal) / riskPrice : (maePriceFinal - entry) / riskPrice
      : null

    return {
      mfePrice: mfePriceFinal,
      maePrice: maePriceFinal,
      mfePct: mfePctCalc,
      maePct: maePctCalc
    }
  }, [seriesData, trade.entryprice, trade.entrytime, trade.exittime, trade.exitprice, trade.risk_price, trade.sl, isBuy])

  if (seriesData.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center rounded-xl border border-white/5"
        style={{ background: 'rgba(255,255,255,0.02)' }}>
        <div className="text-center">
          <div className="text-2xl mb-2"></div>
          <p className="text-slate-500 text-sm">No intraday data from MT5 node</p>
          <p className="text-slate-700 text-xs mt-1">Ensure the MT5 terminal is running</p>
        </div>
      </div>
    )
  }

  // ─── Chart timestamps ───────────────────────────────────────────────
  const dates = seriesData.map(item => {
    const clean = item.time.replace(' ', 'T')
    const d = new Date(clean.endsWith('Z') ? clean : clean + 'Z')
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })
  })
  const values = seriesData.map(item => [item.open, item.close, item.low, item.high])

  // ─── Entry/Exit pin positions ─────────────────────────────────────
  const parseUTC = (str: string) => {
    if (!str) return 0
    const clean = str.replace(' ', 'T')
    return new Date(clean.endsWith('Z') ? clean : clean + 'Z').getTime()
  }

  const entryTime = parseUTC(trade.entrytime)
  const exitTime = parseUTC(trade.exittime)

  const entryIdx = seriesData.reduce((best, bar, i) => {
    const diff = Math.abs(parseUTC(bar.time) - entryTime)
    return diff < Math.abs(parseUTC(seriesData[best].time) - entryTime) ? i : best
  }, 0)

  const exitIdx = seriesData.reduce((best, bar, i) => {
    const diff = Math.abs(parseUTC(bar.time) - exitTime)
    return diff < Math.abs(parseUTC(seriesData[best].time) - exitTime) ? i : best
  }, seriesData.length - 1)

  const markLines: Array<Record<string, unknown>> = [
    {
      name: 'Entry',
      yAxis: trade.entryprice,
      lineStyle: { color: 'rgba(59,130,246,0.45)', type: 'dashed', width: 1.5 },
      label: { show: true, formatter: `ENTRY ${trade.entryprice?.toFixed(2)}`, position: 'insideStartTop', color: '#60A5FA', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }
    }
  ]

  if (trade.sl > 0) {
    markLines.push({
      name: 'Stop Loss',
      yAxis: trade.sl,
      lineStyle: { color: 'rgba(244,63,94,0.35)', type: 'dotted', width: 1.5 },
      label: { show: true, formatter: `SL ${trade.sl?.toFixed(2)}`, position: 'insideStartBottom', color: '#F87171', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }
    })
  }

  if (mfePrice !== null) {
    markLines.push({
      name: 'MFE',
      yAxis: mfePrice,
      lineStyle: { color: 'rgba(16,185,129,0.35)', type: 'dotted', width: 1.5 },
      label: { show: true, formatter: mfePct != null ? `MFE +${mfePct.toFixed(2)}R` : 'MFE (price)', position: 'insideEndTop', color: '#34D399', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }
    })
  }

  if (maePrice !== null) {
    markLines.push({
      name: 'MAE',
      yAxis: maePrice,
      lineStyle: { color: 'rgba(251,113,133,0.35)', type: 'dotted', width: 1.5 },
      label: { show: true, formatter: maePct != null ? `MAE -${maePct.toFixed(2)}R` : 'MAE (price)', position: 'insideEndBottom', color: '#FB7185', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }
    })
  }

  const option = {
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 500,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: 'rgba(255,255,255,0.1)', type: 'dashed' } },
      backgroundColor: 'rgba(11,14,22,0.97)',
      borderColor: 'rgba(59,130,246,0.25)',
      borderWidth: 1,
      borderRadius: 8,
      padding: [10, 14],
      textStyle: { color: '#94A3B8', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' },
      formatter: (params: Array<{ data?: [number, number, number, number]; axisValue?: string }>) => {
        const p = params[0]
        if (!p  !p.data) return ''
        const [o, c, l, h] = p.data
        const dir = c >= o ? '#10B981' : '#F43F5E'
        return `<div style="font-family:JetBrains Mono,monospace; font-size:11px; line-height:1.8">
          <div style="color:#94A3B8; margin-bottom:4px">${p.axisValue ?? ''}</div>
          <div style="color:#64748B">O: <span style="color:${dir}">${o?.toFixed(2)}</span> &nbsp; H: <span style="color:${dir}">${h?.toFixed(2)}</span></div>
          <div style="color:#64748B">L: <span style="color:${dir}">${l?.toFixed(2)}</span> &nbsp; C: <span style="color:${dir}">${c?.toFixed(2)}</span></div>
        </div>`
      }
    },
    grid: { left: 64, right: 64, top: 16, bottom: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      scale: true,
      boundaryGap: true,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      splitLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#475569',
        fontSize: 10,
        fontFamily: 'JetBrains Mono, monospace',
        interval: Math.floor(dates.length / 6)
      }
    },
    yAxis: {
      scale: true,
      position: 'right',
      splitArea: { show: false },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)', type: 'dashed' } },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#475569',
        fontSize: 10,
        fontFamily: 'JetBrains Mono, monospace',
        formatter: (v: number) => v.toFixed(0)
      }
    },
    series: [
      {
        type: 'candlestick',
        data: values,
        itemStyle: {
          color: '#10B981',      // bullish fill
          color0: '#F43F5E',     // bearish fill
          borderColor: '#10B981',
          borderColor0: '#F43F5E',
          borderWidth: 1.5
        },
        markPoint: {
          symbolSize: 36,
          label: { fontSize: 9, fontWeight: 'bold', fontFamily: 'JetBrains Mono, monospace' },
          data: [
            {
              name: 'Entry',
              coord: [dates[entryIdx], trade.entryprice],
              value: 'IN',
              symbol: 'triangle',
              symbolRotate: isBuy ? 0 : 180,
              itemStyle: { color: '#3B82F6', borderColor: '#1D4ED8', borderWidth: 1 },
              label: { color: '#fff' }
            },
            {
              name: 'Exit',
              coord: [dates[exitIdx], trade.exitprice],
              value: 'OUT',
              symbol: 'pin',
              itemStyle: { color: '#8B5CF6', borderColor: '#6D28D9', borderWidth: 1 },
              label: { color: '#fff' }
            }
          ]
        },
        markLine: {
          symbol: ['none', 'none'],
          lineStyle: { width: 1 },
          label: { fontFamily: 'JetBrains Mono, monospace' },
          data: markLines
        }
      }
    ]
  }

  return (
    <div className="space-y-3">
      {/* MFE/MAE computed from M1 data — summary bar */}
      <div className="flex gap-3">
        <div className="flex-1 rounded-lg px-4 py-2.5 flex items-center justify-between"
          style={{ background: 'rgba(16,185,129,0.07)', border: '1px solid rgba(16,185,129,0.15)' }}>
          <div>
            <p className="label-xs text-emerald-600 mb-0.5">Max Fav. Excursion (MFE)</p>
            <p className="font-data text-emerald-400 font-semibold text-base">{mfePct != null ? `+${mfePct.toFixed(3)}R` : 'Price only'}</p>
          </div>
          <div className="text-right">
            <p className="label-xs text-slate-600 mb-0.5">Price</p>
            <p className="font-data text-slate-400 text-xs">{mfePrice?.toFixed(2) ?? '—'}</p>
          </div>
        </div>
        <div className="flex-1 rounded-lg px-4 py-2.5 flex items-center justify-between"
          style={{ background: 'rgba(244,63,94,0.07)', border: '1px solid rgba(244,63,94,0.15)' }}>
          <div>
            <p className="label-xs text-rose-600 mb-0.5">Max Adv. Excursion (MAE)</p>
            <p className="font-data text-rose-400 font-semibold text-base">{maePct != null ? `-${maePct.toFixed(3)}R` : 'Price only'}</p>
          </div>
          <div className="text-right">
            <p className="label-xs text-slate-600 mb-0.5">Price</p>
            <p className="font-data text-slate-400 text-xs">{maePrice?.toFixed(2) ?? '—'}</p>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div style={{ height: 380 }}>
        <ReactECharts
          option={option}
          style={{ height: '100%', width: '100%' }}
          notMerge={true}
          opts={{ renderer: 'svg' }}
        />
      </div>

      {/* Efficiency score */}
      {mfePct != null && mfePct > 0 && trade.r_multiple != null && (
        <div className="rounded-lg px-4 py-2 flex items-center gap-4"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
          <p className="label-xs">Capture Efficiency</p>
          <div className="flex-1 gauge-track">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${Math.min((trade.r_multiple / mfePct) * 100, 100)}%`,
                background: trade.r_multiple / mfePct > 0.6 ? '#10B981' : '#F59E0B'
              }}
            />
          </div>
          <p className="font-data text-sm font-semibold text-slate-300">
            {((trade.r_multiple / mfePct) * 100).toFixed(1)}%
          </p>
          <p className="text-xs text-slate-600">of MFE captured</p>
        </div>
      )}
    </div>
  )
})

export default TradeM1Chart;
