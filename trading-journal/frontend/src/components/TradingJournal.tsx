'use client'

import { useState, useEffect } from 'react'
import { 
  BookOpen, Clock, ChevronRight, Brain, Heart, 
  MessageSquare, Save, Sparkles, RefreshCw,
  Target, ArrowRight
} from 'lucide-react'
import { clsx } from 'clsx'
import { motion } from 'framer-motion'
import { buildApiUrl } from '@/lib/api'

const EMOTIONAL_TAGS = [
  { label: 'Calma', color: '#00C9A7', bg: 'rgba(0, 201, 167, 0.12)' },
  { label: 'Confianza', color: '#6C7BF2', bg: 'rgba(108, 123, 242, 0.12)' },
  { label: 'Disciplina', color: '#40C4FF', bg: 'rgba(64, 196, 255, 0.12)' },
  { label: 'Ansiedad', color: '#FFB547', bg: 'rgba(255, 181, 71, 0.12)' },
  { label: 'FOMO', color: '#FF5252', bg: 'rgba(255, 82, 82, 0.12)' },
  { label: 'Revancha', color: '#FF5252', bg: 'rgba(255, 82, 82, 0.12)' },
  { label: 'Codicia', color: '#FFB547', bg: 'rgba(255, 181, 71, 0.12)' },
  { label: 'Miedo', color: '#A78BFA', bg: 'rgba(167, 139, 250, 0.12)' },
]

const TIMEFRAMES = ['1M', '5M', '15M', '30M', '1H', '4H', 'D1', 'W1', 'MN']

interface PendingTrade {
  position_id: number
  symbol: string
  direction: string
  entrytime: string
  exittime: string
  netpnl: number
  r_multiple: number  null
  volume: number
  entryprice: number
  exitprice: number
  partials?: string
}

interface JournalData {
  emotional_state: number
  emotional_tags: string
  notes_pre: string
  notes_during: string
  notes_post: string
  notes_general: string
  timeframe_data: string
  is_completed: boolean
}

// ── Pending Trades List ──────────────────────────────────────────────────

function PendingTradeCard({ trade, onClick }: { trade: PendingTrade; onClick: () => void }) {
  const pnl = trade.netpnl  0
  return (
    <motion.button
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      onClick={onClick}
      className="glass-card p-4 w-full text-left group hover:border-[rgba(59,130,246,0.3)] transition-all"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full animate-pulse-glow ${pnl >= 0 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]'}`}
            style={{ background: pnl >= 0 ? 'var(--c-positive)' : 'var(--c-negative)' }}
          />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-[var(--text-primary)]">{trade.symbol}</span>
              {trade.partials && trade.partials !== '[]' && (
                <span className="flex items-center justify-center w-3.5 h-3.5 rounded-full bg-[var(--c-info-dim)] text-[var(--c-info)] text-[8px] font-black border border-[rgba(139,92,246,0.2)]" title="Parciales detectados">
                  P
                </span>
              )}
              <span className={clsx(
                'px-2 py-0.5 rounded text-[9px] font-black uppercase',
                trade.direction === 'Buy' ? 'bg-[#40C4FF]/15 text-[#40C4FF]' : 'bg-[#FFB547]/15 text-[#FFB547]'
              )}>{trade.direction}</span>
              <span className="text-[9px] text-[var(--text-ghost)] font-data">
                #{trade.position_id}
              </span>
            </div>
            <p className="text-[10px] text-[var(--text-muted)] mt-0.5 font-data">
              {new Date(trade.entrytime).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })} · 
              Vol {trade.volume} · 
              {trade.entryprice.toFixed(2)} → {trade.exitprice.toFixed(2)}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className={clsx('text-sm font-bold font-data', pnl >= 0 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
            </p>
            {trade.r_multiple != null && (
              <p className="text-[10px] font-data text-[var(--text-muted)]">{Number(trade.r_multiple).toFixed(2)}R</p>
            )}
          </div>
          <ChevronRight className="w-4 h-4 text-[var(--text-ghost)] group-hover:text-[var(--c-neutral)] transition-colors" />
        </div>
      </div>
    </motion.button>
  )
}

// ── Journal Entry Form ───────────────────────────────────────────────────

function JournalForm({
  trade,
  onBack,
  accountLogin,
  serverName,
}: {
  trade: PendingTrade
  onBack: () => void
  accountLogin: string  null
  serverName: string  null
}) {
  const [journal, setJournal] = useState<JournalData>({
    emotional_state: 5,
    emotional_tags: '',
    notes_pre: '',
    notes_during: '',
    notes_post: '',
    notes_general: '',
    timeframe_data: '{}',
    is_completed: false,
  })
  const [tfData, setTfData] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [aiReview, setAiReview] = useState<string  null>(null)
  const [loadingAi, setLoadingAi] = useState(false)
  const pnl = trade.netpnl  0

  // Load existing journal data
  useEffect(() => {
    fetch(buildApiUrl(`/journal/${trade.position_id}`, {
      account_login: accountLogin ?? undefined,
      server_name: serverName ?? undefined,
    }))
      .then(r => r.json())
      .then(data => {
        if (data.journal && data.journal.position_id) {
          setJournal(data.journal)
          try { setTfData(JSON.parse(data.journal.timeframe_data  '{}')) } catch { /* empty */ }
        }
      })
      .catch(() => {})
  }, [trade.position_id, accountLogin, serverName])

  const selectedTags = journal.emotional_tags ? journal.emotional_tags.split(',').filter(Boolean) : []

  const toggleTag = (tag: string) => {
    const tags = new Set(selectedTags)
    if (tags.has(tag)) tags.delete(tag)
    else tags.add(tag)
    setJournal({ ...journal, emotional_tags: Array.from(tags).join(',') })
  }

  const saveJournal = async (complete: boolean) => {
    setSaving(true)
    try {
      await fetch(buildApiUrl(`/journal/${trade.position_id}`, {
        account_login: accountLogin ?? undefined,
        server_name: serverName ?? undefined,
      }), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...journal,
          timeframe_data: tfData,
          is_completed: complete,
        })
      })
    } catch (e) {
      console.error('Failed to save journal', e)
    } finally {
      setSaving(false)
    }
  }

  const requestAiReview = async () => {
    setLoadingAi(true)
    try {
      const res = await fetch(buildApiUrl(`/journal/${trade.position_id}/ai_review`, {
        account_login: accountLogin ?? undefined,
        server_name: serverName ?? undefined,
      }))
      if (res.ok) {
        const data = await res.json()
        setAiReview(data.answer  data.content  JSON.stringify(data))
      }
    } catch (e) {
      console.error('AI review failed', e)
    } finally {
      setLoadingAi(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      className="space-y-4"
    >
      {/* Trade Header (Locked/Pre-filled from MT5) */}
      <div className="glass-card-premium p-5">
        <div className="flex items-center justify-between mb-4">
          <button onClick={onBack} className="text-[10px] text-[var(--c-neutral)] font-bold uppercase tracking-wider hover:underline">
            ← Volver a pendientes
          </button>
          <span className="text-[9px] text-[var(--text-ghost)] font-data">Position #{trade.position_id}</span>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {[
            { label: 'Símbolo', value: trade.symbol },
            { label: 'Dirección', value: trade.direction === 'Buy' ? 'Compra' : 'Venta' },
            { label: 'Volumen', value: trade.volume.toFixed(2) },
            { label: 'Entrada', value: trade.entryprice.toFixed(5) },
            { label: 'Salida', value: trade.exitprice.toFixed(5) },
            { label: 'P&L Neto', value: `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`, color: pnl >= 0 ? 'var(--c-positive)' : 'var(--c-negative)' },
          ].map(item => (
            <div key={item.label} className="p-3 rounded-lg bg-[var(--bg-void)] border border-[var(--bg-border)]">
              <p className="text-[8px] text-[var(--text-ghost)] uppercase font-bold tracking-wider mb-1">{item.label}</p>
              <p className="text-sm font-bold font-data" style={{ color: item.color  'var(--text-primary)' }}>{item.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Partial Exits History */}
      {trade.partials && trade.partials !== '[]' && (
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-[var(--c-neutral)]" />
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Historial de Ejecuciones (Parciales)</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--bg-border)]">
                  <th className="py-2 text-[10px] uppercase font-bold text-[var(--text-ghost)] tracking-wider">Fecha / Hora</th>
                  <th className="py-2 text-[10px] uppercase font-bold text-[var(--text-ghost)] tracking-wider text-right">Volumen</th>
                  <th className="py-2 text-[10px] uppercase font-bold text-[var(--text-ghost)] tracking-wider text-right">Precio Salida</th>
                  <th className="py-2 text-[10px] uppercase font-bold text-[var(--text-ghost)] tracking-wider text-right">Comisión</th>
                  <th className="py-2 text-[10px] uppercase font-bold text-[var(--text-ghost)] tracking-wider text-right">PnL Parcial</th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  try {
                    interface Partial {
                      ticket: number;
                      volume: number;
                      price: number;
                      commission: number;
                      profit: number;
                      time: string;
                    }
                    const partials = JSON.parse(trade.partials) as Partial[];
                    return partials.map((p, idx) => (
                      <tr key={p.ticket  idx} className="border-b border-[var(--bg-border)] last:border-0 hover:bg-[var(--bg-hover)] transition-colors">
                        <td className="py-2 text-xs font-data text-[var(--text-secondary)]">{p.time}</td>
                        <td className="py-2 text-xs font-data text-[var(--text-primary)] font-bold text-right">{p.volume.toFixed(2)}</td>
                        <td className="py-2 text-xs font-data text-[var(--text-secondary)] text-right">{p.price.toFixed(5)}</td>
                        <td className="py-2 text-xs font-data text-[var(--text-secondary)] text-right">{p.commission.toFixed(2)}</td>
                        <td className={clsx('py-2 text-xs font-data font-bold text-right', p.profit >= 0 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
                          {p.profit >= 0 ? '+' : ''}{p.profit.toFixed(2)}
                        </td>
                      </tr>
                    ));
                  } catch {
                    return <tr><td colSpan={5} className="py-2 text-xs text-[var(--text-muted)] text-center">Error al cargar parciales</td></tr>;
                  }
                })()}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Emotional Analysis */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Heart className="w-4 h-4 text-[#FF5252]" />
          <h3 className="text-sm font-bold text-[var(--text-primary)]">Análisis Emocional</h3>
        </div>

        {/* Emotional Slider */}
        <div className="mb-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider">Estado emocional</span>
            <span className="font-data text-lg font-bold text-[var(--text-primary)]">{journal.emotional_state}/10</span>
          </div>
          <input
            type="range" min={1} max={10} value={journal.emotional_state}
            onChange={(e) => setJournal({ ...journal, emotional_state: parseInt(e.target.value) })}
            className="w-full accent-[var(--c-neutral)]"
          />
          <div className="flex justify-between text-[9px] text-[var(--text-ghost)] mt-1">
            <span>Pésimo</span>
            <span>Óptimo</span>
          </div>
        </div>

        {/* Emotion Tags */}
        <div className="flex flex-wrap gap-2">
          {EMOTIONAL_TAGS.map(tag => {
            const active = selectedTags.includes(tag.label)
            return (
              <button
                key={tag.label}
                onClick={() => toggleTag(tag.label)}
                className="emotion-tag"
                style={{
                  background: active ? tag.bg : 'var(--bg-void)',
                  color: active ? tag.color : 'var(--text-muted)',
                  borderColor: active ? tag.color : 'transparent',
                  boxShadow: active ? `0 0 8px ${tag.bg}` : 'none',
                }}
              >
                {tag.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Multi-Timeframe Analysis */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Target className="w-4 h-4 text-[var(--c-info)]" />
          <h3 className="text-sm font-bold text-[var(--text-primary)]">Análisis Multi-Timeframe</h3>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {TIMEFRAMES.map(tf => (
            <div key={tf} className="p-3 rounded-lg bg-[var(--bg-void)] border border-[var(--bg-border)]">
              <p className="text-[10px] font-black text-[var(--c-neutral)] uppercase tracking-wider mb-2">{tf}</p>
              <textarea
                rows={3}
                placeholder={`¿Qué observas en ${tf}?`}
                value={tfData[tf]  ''}
                onChange={(e) => setTfData({ ...tfData, [tf]: e.target.value })}
                className="w-full bg-transparent text-xs text-[var(--text-secondary)] placeholder:text-[var(--text-ghost)] resize-none outline-none"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Qualitative Notes */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare className="w-4 h-4 text-[var(--c-accent)]" />
          <h3 className="text-sm font-bold text-[var(--text-primary)]">Bitácora del Trade</h3>
        </div>

        <div className="space-y-4">
          {[
            { key: 'notes_pre', label: 'Notas Pre-Trade', hint: '¿Cuál era tu plan antes de entrar?' },
            { key: 'notes_during', label: 'Notas Durante', hint: '¿Qué sentiste y observaste durante la ejecución?' },
            { key: 'notes_post', label: 'Notas Post-Trade', hint: 'Reflexión sobre la ejecución y resultado.' },
            { key: 'notes_general', label: 'Conclusiones', hint: '¿Qué mejorarías para la próxima?' },
          ].map(({ key, label, hint }) => (
            <div key={key}>
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1">{label}</p>
              <textarea
                rows={3}
                placeholder={hint}
                value={(journal as unknown as Record<string, string>)[key]  ''}
                onChange={(e) => setJournal({ ...journal, [key]: e.target.value })}
                className="w-full bg-[var(--bg-void)] border border-[var(--bg-border)] rounded-lg p-3 text-xs text-[var(--text-secondary)] placeholder:text-[var(--text-ghost)] resize-none outline-none focus:border-[rgba(59,130,246,0.3)] transition-colors"
              />
            </div>
          ))}
        </div>
      </div>

      {/* AI Review */}
      {aiReview && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card-premium p-5"
        >
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-[var(--c-accent)]" />
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Mentoría Black Knight IA</h3>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">{aiReview}</p>
        </motion.div>
      )}

      {/* Action Bar */}
      <div className="flex items-center justify-between p-4 glass-card">
        <button onClick={requestAiReview} disabled={loadingAi} className="glass-button">
          {loadingAi ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
          {loadingAi ? 'Analizando...' : 'Pedir Revisión IA'}
        </button>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => saveJournal(false)}
            disabled={saving}
            className="glass-button"
          >
            <Save className="w-3 h-3" />
            Guardar Borrador
          </button>
          <button
            onClick={() => saveJournal(true)}
            disabled={saving}
            className="inline-flex items-center gap-1.5 bg-[var(--c-positive)] hover:opacity-90 text-white px-4 py-2 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-colors"
          >
            <ArrowRight className="w-3 h-3" />
            Completar Entrada
          </button>
        </div>
      </div>
    </motion.div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────

interface BehaviorRow {
  tag_list: string
  count: number
  avg_r: number
  win_rate: number
}

interface TradingJournalProps {
  behavior?: BehaviorRow[]
  accountLogin: string  null
  serverName: string  null
}

export default function TradingJournal({ behavior, accountLogin, serverName }: TradingJournalProps) {
  const [pending, setPending] = useState<PendingTrade[]>([])
  const [selectedTrade, setSelectedTrade] = useState<PendingTrade  null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(buildApiUrl('/journal/pending', {
      account_login: accountLogin ?? undefined,
      server_name: serverName ?? undefined,
    }))
      .then(r => r.json())
      .then(data => setPending(Array.isArray(data) ? data : []))
      .catch(() => setPending([]))
      .finally(() => setLoading(false))
  }, [accountLogin, serverName])

  if (selectedTrade) {
    return (
      <JournalForm
        trade={selectedTrade}
        onBack={() => setSelectedTrade(null)}
        accountLogin={accountLogin}
        serverName={serverName}
      />
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Header */}
      <div className="glass-card-premium p-5">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-[rgba(99,102,241,0.1)]">
            <BookOpen className="w-5 h-5 text-[var(--c-accent)]" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Trading Journal</h3>
            <p className="text-[10px] text-[var(--text-muted)] font-medium">
              {pending.length} trades pendientes de revisión · Análisis conductual activo
            </p>
          </div>
        </div>
      </div>

      {/* Behavioral Analytics Matrix */}
      {behavior && behavior.length > 0 && (
        <div className="glass-card-premium overflow-hidden">
          <div className="px-5 py-3 border-b border-[var(--bg-border)] bg-[var(--bg-surface)] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-[var(--c-positive)]" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-secondary)]">Analítica Conductual</span>
            </div>
            <span className="text-[9px] font-bold text-[var(--c-positive)] uppercase">Correlación Emoción vs R-Múltiple</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--bg-void)] text-[var(--text-muted)] text-[9px] uppercase tracking-widest">
                <tr>
                  <th className="px-5 py-2 font-medium">Estado Emocional</th>
                  <th className="px-5 py-2 font-medium text-right">Muestra</th>
                  <th className="px-5 py-2 font-medium text-right">Win Rate</th>
                  <th className="px-5 py-2 font-medium text-right">Avg R</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--bg-border)]">
                {behavior.map((row, i) => (
                  <tr key={i} className="hover:bg-[var(--bg-hover)] transition-colors">
                    <td className="px-5 py-3">
                      <span className="px-2 py-0.5 rounded-full bg-[var(--bg-surface)] text-[var(--text-primary)] font-bold text-[10px]">
                        {row.tag_list}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right font-data text-[var(--text-muted)]">{row.count} trades</td>
                    <td className="px-5 py-3 text-right font-data">
                      <span className={clsx(row.win_rate >= 0.5 ? "text-emerald-400" : "text-rose-400")}>
                        {(row.win_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className={clsx(
                      "px-5 py-3 text-right font-data font-bold",
                      row.avg_r > 0 ? "text-emerald-400" : "text-rose-400"
                    )}>
                      {row.avg_r > 0 ? '+' : ''}{row.avg_r.toFixed(2)}R
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pending Trades */}
      {loading ? (
        <div className="glass-card p-8 text-center">
          <RefreshCw className="w-5 h-5 text-[var(--c-neutral)] animate-spin mx-auto mb-3" />
          <p className="text-xs text-[var(--text-muted)]">Cargando trades pendientes...</p>
        </div>
      ) : pending.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <BookOpen className="w-6 h-6 text-[var(--text-ghost)] mx-auto mb-3" />
          <p className="text-sm font-bold text-[var(--text-secondary)] mb-1">Todo al día</p>
          <p className="text-[11px] text-[var(--text-muted)]">No hay trades pendientes de revisión en los últimos 30 días.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {pending.map((trade) => (
            <PendingTradeCard 
              key={trade.position_id} 
              trade={trade} 
              onClick={() => setSelectedTrade(trade)} 
            />
          ))}
        </div>
      )}
    </motion.div>
  )
}
