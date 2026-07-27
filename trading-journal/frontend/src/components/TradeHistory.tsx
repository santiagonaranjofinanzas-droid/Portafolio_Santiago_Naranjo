'use client'
import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { ChevronDown, ChevronUp, Filter } from 'lucide-react'
import type { TradeDetail } from './TradeDetailDrawer'

interface Trade {
  position_id: number;
  symbol: string;
  netpnl: number;
  r_multiple: number;
  volume: number;
  exittime: number  string;
  direction?: string;
  type_op?: number;
}

type SortKey = 'exittime'  'symbol'  'netpnl'  'r_multiple'  'volume'
type SortDir = 'asc'  'desc'

const SortIcon = ({ k, sortKey, sortDir }: { k: SortKey, sortKey: SortKey, sortDir: SortDir }) => 
  sortKey === k ? (sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : null

interface Props {
  data: Trade[];
  onTradeClick?: (trade: TradeDetail) => void;
}

export default function TradeHistory({ data, onTradeClick }: Props) {
  const [filter, setFilter] = useState<'all''win''loss'>('all')
  const [sortKey, setSortKey] = useState<SortKey>('exittime')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(0)
  const perPage = 15

  const trades = useMemo(() => {
    if (!data?.length) return []
    let filtered = data.filter((t: Trade) => Number(t.type_op ?? 0) !== 2)
    if (filter === 'win') filtered = filtered.filter((t: Trade) => Number(t.netpnl ?? 0) > 0)
    if (filter === 'loss') filtered = filtered.filter((t: Trade) => Number(t.netpnl ?? 0) < 0)
    filtered.sort((a: Trade, b: Trade) => {
      const av = a[sortKey], bv = b[sortKey]
      if (sortKey === 'exittime'  sortKey === 'symbol') { 
        const as = String(av ?? ''); 
        const bs = String(bv ?? ''); 
        return sortDir === 'asc' ? as.localeCompare(bs) : bs.localeCompare(as) 
      }
      return sortDir === 'asc' ? Number(av ?? 0) - Number(bv ?? 0) : Number(bv ?? 0) - Number(av ?? 0)
    })
    return filtered
  }, [data, filter, sortKey, sortDir])

  const totalPages = Math.max(1, Math.ceil(trades.length / perPage))
  const paginated = trades.slice(page * perPage, (page + 1) * perPage)

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const fmtDate = (v: unknown) => {
    if (!v) return '—'
    const d = typeof v === 'number' ? new Date(v > 1e12 ? v : v * 1000) : new Date(String(v))
    return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('es-ES', { day:'2-digit', month:'short' }) + ' ' + d.toLocaleTimeString('es-ES', { hour:'2-digit', minute:'2-digit' })
  }

  if (!data?.length) return null

  return (
    <div className="widget">
      <div className="widget-header">
        <div className="widget-title"><Filter className="widget-title-icon" />Historial de Trades</div>
        <div className="flex items-center gap-1">
          {(['all','win','loss'] as const).map(f => (
            <button key={f} onClick={() => { setFilter(f); setPage(0) }}
              className={clsx('period-tab', filter === f && 'active')}>
              {f === 'all' ? 'Todos' : f === 'win' ? 'Ganadores' : 'Perdedores'}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th onClick={() => toggleSort('exittime')}>Fecha <SortIcon k="exittime" sortKey={sortKey} sortDir={sortDir} /></th>
              <th onClick={() => toggleSort('symbol')}>Símbolo <SortIcon k="symbol" sortKey={sortKey} sortDir={sortDir} /></th>
              <th>Dir</th>
              <th onClick={() => toggleSort('volume')}>Lotes <SortIcon k="volume" sortKey={sortKey} sortDir={sortDir} /></th>
              <th onClick={() => toggleSort('netpnl')}>PnL <SortIcon k="netpnl" sortKey={sortKey} sortDir={sortDir} /></th>
              <th onClick={() => toggleSort('r_multiple')}>R-Mult <SortIcon k="r_multiple" sortKey={sortKey} sortDir={sortDir} /></th>
            </tr>
          </thead>
          <tbody>
            {paginated.map((t: Trade, i: number) => {
              const pnl = Number(t.netpnl ?? 0)
              const rMul = Number(t.r_multiple ?? 0)
              const dirRaw = String(t.direction ?? (Number(t.type_op) === 0 ? 'Buy' : 'Sell'))
              const dir = dirRaw === 'Buy' ? 'Compra' : 'Venta'
              return (
                <tr key={`${t.position_id}-${i}`} onClick={() => onTradeClick?.(t as unknown as TradeDetail)}>
                  <td className="font-data text-xs">{fmtDate(t.exittime)}</td>
                  <td className="font-semibold text-xs" style={{color:'var(--text-primary)'}}>{String(t.symbol ?? '—')}</td>
                  <td><span className={clsx('trade-badge', dirRaw === 'Buy' ? 'trade-badge--buy' : 'trade-badge--sell')}>{dir}</span></td>
                  <td className="font-data text-xs">{Number(t.volume ?? 0).toFixed(2)}</td>
                  <td className={clsx('font-data text-xs font-semibold', pnl >= 0 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                  </td>
                  <td className={clsx('font-data text-xs', rMul >= 0 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
                    {rMul.toFixed(2)}R
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t" style={{borderColor:'var(--bg-border)'}}>
          <span className="text-xs" style={{color:'var(--text-muted)'}}>{trades.length} operaciones</span>
          <div className="flex items-center gap-2">
            <button className="btn btn-ghost text-xs" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>Anterior</button>
            <span className="text-xs font-data" style={{color:'var(--text-secondary)'}}>{page + 1}/{totalPages}</span>
            <button className="btn btn-ghost text-xs" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}>Siguiente</button>
          </div>
        </div>
      )}
    </div>
  )
}
