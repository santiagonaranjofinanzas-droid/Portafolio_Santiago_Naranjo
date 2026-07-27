'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Brain,
  Database,
  Loader2,
  MessageSquareQuote,
  Send,
  Shield,
  Sparkles,
  Target,
} from 'lucide-react'
import { clsx } from 'clsx'
import { buildApiUrl } from '@/lib/api'
import type { AiChatMessage, AiSeed } from '@/lib/ai'

type DashboardTrade = {
  position_id?: number
  symbol?: string
  direction?: string
  entrytime?: string
  netpnl?: number  string  null
  r_multiple?: number  string  null
  exit_reason?: number  string  null
  volume?: number  string  null
  commission?: number  string  null
  partials?: string  null // JSON string array
  planned_tp?: number  null
  planned_max_r?: number  null
  what_if_result?: string  null
  what_if_pnl?: number  null
  what_if_r?: number  null
}

type DashboardStats = {
  summary?: {
    sqn?: number  null
    expectancy?: number  null
    sharpe?: number  null
    net_profit?: number  null
    start_cap?: number  null
  }
  perf?: {
    pf?: number  null
    calmar?: number  null
    win_rate?: number  null
    max_drawdown?: number  null
    recovery_factor?: number  null
    tail_ratio?: number  null
  }
  risk?: {
    var?: number  null
    cvar?: number  null
    cf_var?: number  null
    garch_var?: number  null
    vol_regime?: string  null
  }
  quant?: {
    psr?: number  null
    significance?: string  null
    runs_zscore?: number  null
    serial_independent?: boolean  null
    mc_dd_p10?: number  null
    mc_dd_p1?: number  null
    prob_ruin_10pct?: number  null
    prob_ruin_20pct?: number  null
    commission_drag_pct?: number  null
  }
  account_snapshot?: {
    balance?: number  null
    equity?: number  null
    currency?: string  null
    account_login?: string  null
    server_name?: string  null
  }
  history?: DashboardTrade[]
}

type AiResponsePayload = {
  answer?: string
  provider?: string
  model?: string
  context_as_of?: string
  sources?: string[]
  warnings?: string[]
}

interface AIAnalystPanelProps {
  stats?: DashboardStats
  selectedBot: number  null
  accountLogin: string  null
  serverName: string  null
  seed: AiSeed  null
}

function formatMoney(value: number  null  undefined): string {
  const number = Number(value ?? 0)
  return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatPercent(value: number  null  undefined): string {
  const number = Number(value ?? 0)
  return `${(number * 100).toFixed(2)}%`
}

function formatNumber(value: number  null  undefined, digits = 2): string {
  const number = Number(value ?? 0)
  return number.toFixed(digits)
}

const MAX_PROMPT_CHARS = 4000
const MAX_MESSAGE_CHARS = 4000

function clampText(value: string, limit: number): string {
  if (value.length <= limit) return value
  return `${value.slice(0, limit)}...`
}

function parseInlineElements(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*.*?\*\*`.*?`)/g)
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index} className="font-bold text-[var(--text-primary)]">{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index} className="bg-[var(--bg-surface)] border border-[var(--bg-border)] px-1.5 py-0.5 rounded font-mono text-xs text-[var(--c-neutral)]">{part.slice(1, -1)}</code>
    }
    return part
  })
}

function renderMarkdown(content: string): React.ReactNode {
  if (!content) return null

  const parts = content.split(/(```[\s\S]*?```)/g)
  
  return parts.map((part, index) => {
    if (part.startsWith('```')) {
      const match = part.match(/```(\w*)\n([\s\S]*?)```/)
      const lang = match ? match[1] : ''
      const code = match ? match[2] : part.slice(3, -3)
      return (
        <pre key={index} className="bg-black/50 p-4 rounded-xl border border-white/5 font-mono text-xs overflow-x-auto my-3 text-emerald-400">
          {lang && <div className="text-[9px] uppercase tracking-wider text-[var(--text-muted)] mb-2 border-b border-white/5 pb-1 font-bold">{lang}</div>}
          <code>{code}</code>
        </pre>
      )
    }

    const lines = part.split('\n')
    return (
      <div key={index} className="space-y-1.5">
        {lines.map((line, lIdx) => {
          const cleanLine = line.trim()
          
          if (cleanLine.startsWith('- ')  cleanLine.startsWith('* ')) {
            return (
              <ul key={lIdx} className="list-disc pl-5 my-1 text-[var(--text-secondary)]">
                <li>{parseInlineElements(cleanLine.slice(2))}</li>
              </ul>
            )
          }

          const numMatch = cleanLine.match(/^(\d+)\.\s(.*)/)
          if (numMatch) {
            return (
              <ol key={lIdx} className="list-decimal pl-5 my-1 text-[var(--text-secondary)]">
                <li value={Number(numMatch[1])}>{parseInlineElements(numMatch[2])}</li>
              </ol>
            )
          }

          if (cleanLine.startsWith('### ')) {
            return <h4 key={lIdx} className="text-sm font-black text-[var(--text-primary)] uppercase tracking-wider mt-4 mb-2">{parseInlineElements(cleanLine.slice(4))}</h4>
          }
          if (cleanLine.startsWith('## ')) {
            return <h3 key={lIdx} className="text-base font-black text-[var(--text-primary)] tracking-tight mt-5 mb-2">{parseInlineElements(cleanLine.slice(3))}</h3>
          }
          if (cleanLine.startsWith('# ')) {
            return <h2 key={lIdx} className="text-lg font-black text-[var(--text-primary)] tracking-tight mt-6 mb-3">{parseInlineElements(cleanLine.slice(2))}</h2>
          }

          return line ? <p key={lIdx} className="text-sm leading-relaxed text-[var(--text-secondary)]">{parseInlineElements(line)}</p> : <div key={lIdx} className="h-2" />
        })}
      </div>
    )
  })
}

function normalizeMessages(messageList: AiChatMessage[]): AiChatMessage[] {
  return messageList.map((message) => ({
    ...message,
    content: clampText(String(message.content ?? ''), MAX_MESSAGE_CHARS),
  }))
}

function compactTradeSummary(trade: DashboardTrade): string {
  const symbol = trade.symbol  'N/A'
  const direction = trade.direction  'N/A'
  const net = Number(trade.netpnl ?? 0)
  const rMultiple = Number(trade.r_multiple ?? 0)
  
  let partialLabel = ''
  try {
    if (trade.partials && JSON.parse(trade.partials).length > 0) {
      partialLabel = ' [P]'
    }
  } catch {}

  return `${symbol} ${direction}${partialLabel} ${net >= 0 ? '+' : ''}$${formatMoney(net)}  ${rMultiple.toFixed(2)}R`
}

export default function AIAnalystPanel({ stats, selectedBot, accountLogin, serverName, seed }: AIAnalystPanelProps) {
  const [messages, setMessages] = useState<AiChatMessage[]>([
    {
      role: 'assistant',
      content:
        'Analista IA listo. Puedo resumir riesgo, auditar ejecucion, redactar diario o explicar cualquier metrico del tablero.',
    },
  ])
  const [input, setInput] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [status, setStatus] = useState<{
    provider: string
    model: string
    contextAsOf?: string
    sources: string[]
    warnings: string[]
  }  null>(null)
  const seenSeedId = useRef<number  null>(null)

  // Macro context state for the sidebar display
  const [macroContext, setMacroContext] = useState<string  null>(null)
  const [isLoadingMacro, setIsLoadingMacro] = useState(false)

  const focusLabel = seed?.focus  'Analista IA'

  useEffect(() => {
    let active = true
    const fetchMacroContext = async () => {
      setIsLoadingMacro(true)
      try {
        const response = await fetch(buildApiUrl('/ai/macro-context'))
        if (!response.ok) throw new Error('Failed to fetch macro context')
        const data = await response.json()
        if (active && data?.context) {
          setMacroContext(data.context)
        }
      } catch (err) {
        console.error('Error fetching macro context:', err)
      } finally {
        if (active) setIsLoadingMacro(false)
      }
    }
    void fetchMacroContext()
    return () => {
      active = false
    }
  }, [])

  const parsedMacro = useMemo(() => {
    if (!macroContext) return null
    const lines = macroContext.split('\n')
    const data: Record<string, string> = {}
    let narrative = ''
    
    for (const line of lines) {
      if (line.includes('---')) continue
      if (line.startsWith('Narrativa de Mercado (Mirofish):')) {
        narrative = line.replace('Narrativa de Mercado (Mirofish):', '').trim()
        continue
      }
      const parts = line.split(':')
      if (parts.length >= 2) {
        const key = parts[0].trim()
        const val = parts.slice(1).join(':').trim()
        data[key] = val
      }
    }
    return { data, narrative }
  }, [macroContext])

  const contextSnapshot = useMemo(() => {
    const summary = stats?.summary ?? {}
    const perf = stats?.perf ?? {}
    const risk = stats?.risk ?? {}
    const quant = stats?.quant ?? {}
    const account = stats?.account_snapshot ?? {}
    const history = stats?.history ?? []
    const recentTrades = history.slice(-5).map((trade) => ({
      symbol: trade?.symbol,
      direction: trade?.direction,
      netpnl: trade?.netpnl,
      r_multiple: trade?.r_multiple,
      volume: trade?.volume,
    }))

    return {
      active_tab: 'Analista IA',
      focus: focusLabel,
      selected_bot: selectedBot,
      summary,
      perf,
      risk,
      quant,
      account_snapshot: account,
      account_login: accountLogin ?? account.account_login ?? null,
      server_name: serverName ?? account.server_name ?? null,
      recent_trades: recentTrades,
      trade_count: history.length,
    }
  }, [accountLogin, focusLabel, selectedBot, serverName, stats])

  const summaryMetrics = useMemo(() => {
    const summary = stats?.summary ?? {}
    const perf = stats?.perf ?? {}
    const risk = stats?.risk ?? {}
    const quant = stats?.quant ?? {}

    return [
      { label: 'SQN', value: formatNumber(summary.sqn, 2) },
      { label: 'Sharpe', value: formatNumber(summary.sharpe, 2) },
      { label: 'Expectancy', value: `${formatNumber(summary.expectancy, 2)}R` },
      { label: 'PF', value: formatNumber(perf.pf, 2) },
      { label: 'Calmar', value: formatNumber(perf.calmar, 2) },
      { label: 'PSR', value: formatPercent(quant.psr) },
      { label: 'Max DD', value: formatPercent(perf.max_drawdown) },
      { label: 'VaR 99%', value: formatPercent(risk.var) },
    ]
  }, [stats])

  const quickPrompts = useMemo(
    () => [
      {
        label: 'Riesgo',
        prompt:
          `Analiza el perfil de riesgo de la cartera con foco en ${focusLabel}. Explica drawdown, PSR, Calmar y liquidez de riesgo. Devuelve diagnostico, 3 riesgos y 3 acciones concretas.`,
      },
      {
        label: 'Diario',
        prompt:
          `Redacta una entrada automatica de diario de trading para ${focusLabel}. Resume disciplina, comisiones, sesgo de ejecucion y el plan de mejora para la siguiente sesion.`,
      },
      {
        label: 'Ejecucion',
        prompt:
          `Audita la ejecucion reciente del sistema en ${focusLabel}. Correlaciona las operaciones recientes con el coste, el tamaño y las salidas para encontrar patrones repetitivos.`,
      },
      {
        label: 'Macro Intel',
        focus: 'Macro Intel',
        prompt:
          'Analiza el contexto macroeconómico actual de la pestaña Macro Intel. Incluye tu lectura del régimen de mercado (HMM), nivel de estrés, entropía, sesgo dominante y las noticias más relevantes. Sugiere acciones tácticas concretas de posicionamiento.',
      },
    ],
    [focusLabel],
  )

  const requestAi = useCallback(
    async (prompt: string, route: '/ai/chat'  '/ai/insight', overrideFocus?: string) => {
      const trimmed = clampText(prompt.trim(), MAX_PROMPT_CHARS)
      if (!trimmed  isSubmitting) return

      const nextConversation: AiChatMessage[] = normalizeMessages([
        ...messages,
        { role: 'user', content: trimmed },
      ])
      setMessages(nextConversation)
      setInput('')
      setIsSubmitting(true)

      const activeFocus = overrideFocus  focusLabel

      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 60000)

        const response = await fetch(buildApiUrl(route), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            prompt: trimmed,
            focus: activeFocus,
            account_login: accountLogin ?? contextSnapshot.account_login,
            server_name: serverName ?? contextSnapshot.server_name,
            selected_bot: selectedBot,
            context: contextSnapshot,
            messages: nextConversation.slice(-5),
          }),
        })
        clearTimeout(timeoutId)

        const rawBody = await response.text()
        if (!response.ok) {
          const detail = rawBody ? `: ${rawBody.slice(0, 200)}` : ''
          throw new Error(`AI request failed (${response.status})${detail}`)
        }

        let data: AiResponsePayload = {}
        if (rawBody.trim().length > 0) {
          try {
            data = JSON.parse(rawBody) as AiResponsePayload
          } catch {
            throw new Error('Respuesta de IA invalida')
          }
        }

        const rawAnswer = data.answer
        const answer = typeof rawAnswer === 'string' ? rawAnswer.trim() : 'Respuesta no valida del servidor AI.'

        setMessages((current) => [...current, { role: 'assistant', content: answer }])
        setStatus({
          provider: data.provider  'fallback',
          model: data.model  'heuristic',
          contextAsOf: data.context_as_of,
          sources: data.sources  [],
          warnings: data.warnings  [],
        })
      } catch (requestError: unknown) {
        console.error('AI request failed:', requestError)
        const isAbort = requestError instanceof DOMException && requestError.name === 'AbortError'
        setMessages((current) => [
          ...current,
          {
            role: 'assistant',
            content: isAbort 
              ? 'La consulta ha sido cancelada por exceso de tiempo (timeout). Por favor, intenta de nuevo.' 
              : 'Error crítico de conexión con el motor de IA. Por favor, verifica que el servidor esté activo.'
          }
        ])
      } finally {
        setIsSubmitting(false)
      }
    },
    [accountLogin, focusLabel, isSubmitting, messages, contextSnapshot, selectedBot, serverName]
  )

  useEffect(() => {
    if (!seed?.prompt) return
    if (seenSeedId.current === seed.id) return
    seenSeedId.current = seed.id
    void requestAi(seed.prompt, '/ai/insight')
  }, [requestAi, seed?.id, seed?.prompt])

  const sendChat = async () => {
    await requestAi(input, '/ai/chat')
  }

  const latestTradeLabel = useMemo(() => {
    const trades = stats?.history ?? []
    if (trades.length === 0) return 'Sin operaciones recientes'
    return compactTradeSummary(trades[trades.length - 1])
  }, [stats])

  const recentTrades = useMemo(() => {
    const trades = stats?.history ?? []
    return [...trades].slice(-5).reverse()
  }, [stats])

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="space-y-6">
      <section className="glass-card-heavy relative overflow-hidden p-6">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              'radial-gradient(100% 200% at 0% 0%, rgba(124,111,212,0.15) 0%, rgba(124,111,212,0) 50%), radial-gradient(100% 200% at 100% 0%, rgba(75,163,199,0.12) 0%, rgba(75,163,199,0) 50%)',
          }}
        />

        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--c-warning)] animate-pulse shadow-[0_0_8px_rgba(214,174,108,0.5)]" />
              <p className="text-[10px] uppercase tracking-[0.2em] font-black text-[var(--c-warning)] text-glow-gold">
                CENTRO DE MANDO NEURONAL
              </p>
            </div>
            <h2 className="text-3xl font-black tracking-tight text-[var(--text-primary)]">Analista Cuantitativo</h2>
            <p className="max-w-xl text-sm text-[var(--text-secondary)] leading-relaxed">
              Interacción directa con el motor de IA integrado. Diagnósticos, auditoría de ejecución y generación de diario automatizado con contexto real.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-1 text-[10px] uppercase tracking-widest text-[var(--text-secondary)] font-bold">
                Focus: {focusLabel}
              </span>
              <span className="rounded-full border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-1 text-[10px] uppercase tracking-widest text-[var(--text-secondary)] font-bold">
                Node: {selectedBot === null ? 'Global' : selectedBot}
              </span>
              <div className="flex items-center gap-2 rounded-full border px-3 py-1" style={{ borderColor: 'var(--bg-border-strong)', backgroundColor: 'var(--c-positive-dim)' }}>
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                <span className="text-[10px] uppercase tracking-widest text-emerald-400 font-black">
                  {status ? `${status.provider} · ${status.model}` : 'Neural Link Active'}
                </span>
              </div>
              {status?.contextAsOf && (
                <span
                  className="rounded-full border border-[var(--bg-border)] px-3 py-1 text-[10px] text-[var(--text-muted)]"
                  title={`Fuentes: ${status.sources.join(', ')}`}
                >
                  Contexto: {new Date(status.contextAsOf).toLocaleTimeString()}
                </span>
              )}
              {status && status.sources.length > 0 && (
                <span className="rounded-full border border-[var(--bg-border)] px-3 py-1 text-[10px] text-[var(--text-muted)]">
                  Fuentes: {status.sources.length}
                </span>
              )}
            </div>
            {status && status.warnings.length > 0 && (
              <p className="mt-2 text-[10px] text-amber-400/80">
                {status.warnings.join(' · ')}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 lg:min-w-[420px]">
            {summaryMetrics.slice(0, 4).map((metric) => (
              <div key={metric.label} className="p-3 bg-[var(--bg-surface)] border border-[var(--bg-border)] hover:border-[var(--bg-border-strong)] transition-colors rounded-xl">
                <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)] font-bold">{metric.label}</p>
                <p className="mt-1 font-data text-base font-black text-[var(--text-primary)]">{metric.value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-[1.55fr_0.95fr] gap-6">
        <section className="glass-card-heavy flex min-h-[700px] flex-col overflow-hidden p-6">
          <div className="flex items-center justify-between gap-4 border-b border-[var(--bg-border)] pb-6">
            <div className="flex items-center gap-4">
              <div className="h-10 w-10 rounded-xl border flex items-center justify-center" style={{ backgroundColor: 'rgba(139, 92, 246, 0.1)', borderColor: 'var(--bg-border-strong)' }}>
                <Brain className="h-5 w-5 text-[var(--c-info)]" />
              </div>
              <div>
                <h3 className="text-lg font-black text-[var(--text-primary)]">Copiloto Estratégico</h3>
                <p className="text-xs text-[var(--text-muted)] font-medium">Análisis contextual en tiempo real de operaciones y métricas.</p>
              </div>
            </div>
            <div className="hidden md:block text-right">
              <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)] font-bold">Ultimo evento detectado</p>
              <p className="mt-1 font-data text-xs font-bold text-[var(--text-primary)] text-glow-gold">{latestTradeLabel}</p>
            </div>
          </div>

          <div className="mt-6 flex-1 space-y-6 overflow-y-auto pr-2 custom-scrollbar">
            {messages.map((message, index) => (
              <motion.div
                key={`${message.role}-${index}`}
                initial={{ opacity: 0, x: message.role === 'user' ? 20 : -20 }}
                animate={{ opacity: 1, x: 0 }}
                className={clsx('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}
              >
                <div
                  className={clsx(
                    'max-w-[90%] md:max-w-[85%] rounded-2xl p-5 relative group transition-all border shadow-[0_8px_32px_rgba(0,0,0,0.05)]'
                  )}
                  style={
                    message.role === 'user'
                      ? { backgroundColor: 'rgba(139, 92, 246, 0.05)', borderColor: 'rgba(139, 92, 246, 0.15)' }
                      : { backgroundColor: 'var(--bg-elevated)', borderColor: 'var(--bg-border)' }
                  }
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {message.role === 'user' ? (
                        <div className="h-6 w-6 rounded-lg bg-[rgba(139,92,246,0.2)] flex items-center justify-center">
                          <MessageSquareQuote className="h-3.5 w-3.5 text-[var(--c-info)]" />
                        </div>
                      ) : (
                        <div className="h-6 w-6 rounded-lg bg-[rgba(234,179,8,0.2)] flex items-center justify-center">
                          <Sparkles className="h-3.5 w-3.5 text-[var(--c-warning)]" />
                        </div>
                      )}
                      <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        {message.role === 'user' ? 'Terminal User' : 'BK Quant Analyst'}
                      </span>
                    </div>
                    <span className="text-[9px] font-bold text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity">
                      {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div className="text-sm leading-relaxed text-[var(--text-secondary)]">
                    {renderMarkdown(message.content)}
                  </div>
                </div>
              </motion.div>
            ))}

            {isSubmitting && (
              <div className="flex justify-start">
                <div className="rounded-2xl p-5 w-full md:max-w-[85%] border shadow-[0_8px_32px_rgba(0,0,0,0.05)]" style={{ backgroundColor: 'var(--bg-elevated)', borderColor: 'var(--bg-border)' }}>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="relative">
                      <div className="h-6 w-6 rounded-lg flex items-center justify-center" style={{ backgroundColor: 'var(--c-warning-dim)', border: '1px solid var(--bg-border-strong)' }}>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--c-warning)]" />
                      </div>
                      <motion.div
                        animate={{ scale: [1, 1.5, 1], opacity: [0.3, 0.6, 0.3] }}
                        transition={{ repeat: Infinity, duration: 2 }}
                        className="absolute inset-0 rounded-lg blur-md"
                        style={{ backgroundColor: 'rgba(234, 179, 8, 0.25)' }}
                      />
                    </div>
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[var(--c-warning)] animate-pulse">
                      Calculando Diagnóstico...
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                      <motion.div
                        animate={{ x: ['-100%', '100%'] }}
                        transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                        className="h-full w-1/3 bg-gradient-to-r from-transparent via-[var(--c-warning)] to-transparent opacity-40"
                      />
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)] font-medium">Sincronizando telemetría del dashboard y evaluando sesgos de ejecución...</p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 space-y-4">
            <div className="flex flex-wrap gap-2">
              {quickPrompts.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => void requestAi(item.prompt, '/ai/insight', item.focus)}
                  disabled={isSubmitting}
                  className="h-9 px-4 bg-[var(--bg-surface)] border border-[var(--bg-border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-amber-500/10 hover:border-amber-500/30 transition-all rounded-full font-black uppercase text-[9px] tracking-widest flex items-center gap-2"
                >
                  <Sparkles className="h-3.5 w-3.5 text-[var(--c-warning)]" />
                  {item.label}
                </button>
              ))}
            </div>

            <div className="relative bg-[var(--bg-surface)] border border-[var(--bg-border)] p-4 group focus-within:border-purple-500/30 transition-all rounded-2xl">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if ((event.metaKey  event.ctrlKey) && event.key === 'Enter') {
                    event.preventDefault()
                    void sendChat()
                  }
                }}
                rows={3}
                className="w-full resize-none bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] custom-scrollbar"
                placeholder="Consulta sobre riesgo, patrones de ejecución o solicita una entrada de diario..."
              />

              <div className="mt-3 flex items-center justify-between border-t border-[var(--bg-border)] pt-3">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-black/20 border border-[var(--bg-border)]">
                    <kbd className="text-[9px] font-black text-[var(--text-muted)]">CMD</kbd>
                    <span className="text-[9px] text-[var(--text-muted)]">+</span>
                    <kbd className="text-[9px] font-black text-[var(--text-muted)]">ENTER</kbd>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void sendChat()}
                  disabled={isSubmitting  !input.trim()}
                  className="h-10 px-6 bg-purple-600 hover:bg-purple-500 text-white transition-all rounded-xl font-black uppercase text-[10px] tracking-widest flex items-center gap-2 shadow-[0_8px_20px_rgba(139,92,246,0.25)] disabled:opacity-50 disabled:shadow-none"
                >
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Ejecutar Consulta
                </button>
              </div>
            </div>
          </div>
        </section>

        <aside className="space-y-6">
          <section className="glass-card-heavy p-6">
            <div className="flex items-center gap-2 mb-4">
              <Target className="h-4 w-4 text-[var(--c-warning)]" />
              <h3 className="text-sm font-black text-[var(--text-primary)] uppercase tracking-widest">Contexto de Análisis</h3>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {summaryMetrics.map((metric) => (
                <div key={metric.label} className="p-3 bg-[var(--bg-surface)] border border-[var(--bg-border)] hover:bg-[var(--bg-hover)] transition-all group rounded-xl">
                  <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)] font-bold group-hover:text-[var(--text-primary)] transition-colors">{metric.label}</p>
                  <p className="mt-1 font-data text-sm font-black text-[var(--text-primary)]">{metric.value}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="glass-card-heavy p-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-5">
              <Brain className="h-24 w-24" />
            </div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Brain className="h-4 w-4 text-purple-400" />
                <h3 className="text-sm font-black text-[var(--text-primary)] uppercase tracking-widest">Bloomberg Sentinel</h3>
              </div>
              {isLoadingMacro && <Loader2 className="h-3.5 w-3.5 animate-spin text-purple-400" />}
            </div>

            {parsedMacro && Object.keys(parsedMacro.data).length > 0 ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  {parsedMacro.data['Probabilidad de Estrés'] && (
                    <div className="p-2.5 bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-xl">
                      <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)] font-bold">Estrés</p>
                      <p className="mt-0.5 font-data text-xs font-black text-[var(--text-primary)]">
                        {parsedMacro.data['Probabilidad de Estrés']}
                      </p>
                    </div>
                  )}
                  {parsedMacro.data['Regimen Dominante (Market Regime)'] && (
                    <div className="p-2.5 bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-xl">
                      <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)] font-bold">Régimen</p>
                      <p className="mt-0.5 font-data text-xs font-black text-amber-400">
                        {parsedMacro.data['Regimen Dominante (Market Regime)']}
                      </p>
                    </div>
                  )}
                  {parsedMacro.data['Confianza'] && (
                    <div className="p-2.5 bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-xl">
                      <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)] font-bold">Confianza</p>
                      <p className="mt-0.5 font-data text-xs font-black text-[var(--text-primary)]">
                        {parsedMacro.data['Confianza']}
                      </p>
                    </div>
                  )}
                  {parsedMacro.data['Entropía'] && (
                    <div className="p-2.5 bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-xl">
                      <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)] font-bold">Entropía</p>
                      <p className="mt-0.5 font-data text-xs font-black text-[var(--text-primary)]">
                        {parsedMacro.data['Entropía']}
                      </p>
                    </div>
                  )}
                </div>

                {parsedMacro.narrative && (
                  <div className="p-3 bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-xl text-[11px] leading-relaxed text-[var(--text-secondary)]">
                    <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)] font-bold mb-1">Narrativa Sentinel</p>
                    {parsedMacro.narrative}
                  </div>
                )}

                <div className="flex items-center justify-between text-[9px] text-[var(--text-muted)] mt-2">
                  <span>Última Act: {parsedMacro.data['Última Actualización']  'N/A'}</span>
                </div>
              </div>
            ) : (
              <div className="p-4 bg-[var(--bg-surface)] border border-[var(--bg-border)] text-center italic text-xs text-[var(--text-muted)] rounded-xl">
                {isLoadingMacro ? 'Cargando datos del Sentinel...' : 'No hay datos macro disponibles en el Sentinel.'}
              </div>
            )}
          </section>

          <section className="glass-card-heavy p-6">
            <div className="flex items-center gap-2 mb-4">
              <Database className="h-4 w-4 text-[var(--c-info)]" />
              <h3 className="text-sm font-black text-[var(--text-primary)] uppercase tracking-widest">Feed de Operaciones</h3>
            </div>
            <div className="space-y-2.5">
              {recentTrades.length > 0 ? (
                recentTrades.map((trade, index) => {
                  const net = Number(trade.netpnl ?? 0)
                  const isWin = net >= 0
                  return (
                    <button
                      key={`${trade.position_id}-${index}`}
                      type="button"
                      onClick={() => setInput(`Audita la ejecución del trade en ${trade.symbol} (${trade.direction}) con PnL de $${net.toFixed(2)} y ${Number(trade.r_multiple ?? 0).toFixed(2)}R.`)}
                      className={clsx(
                        "w-full text-left p-3 bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)] border border-[var(--bg-border)] text-[11px] font-data text-[var(--text-secondary)] border-l-2 transition-all cursor-pointer block rounded-xl",
                        isWin ? "border-l-[var(--c-positive)]" : "border-l-[var(--c-negative)]"
                      )}
                    >
                      <div className="flex justify-between items-center font-bold">
                        <span className="text-[var(--text-primary)] text-xs">{trade.symbol} · {trade.direction}</span>
                        <span className={clsx(isWin ? "text-[var(--c-positive)]" : "text-[var(--c-negative)]")}>
                          {isWin ? '+' : ''}${net.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-[10px] text-[var(--text-muted)] mt-1">
                        <span>Vol: {Number(trade.volume ?? 0).toFixed(2)}</span>
                        <span>{Number(trade.r_multiple ?? 0).toFixed(2)}R</span>
                      </div>
                    </button>
                  )
                })
              ) : (
                <div className="p-4 bg-[var(--bg-surface)] border border-[var(--bg-border)] text-center italic text-xs text-[var(--text-muted)] rounded-xl">
                  Esperando flujo de datos...
                </div>
              )}
            </div>
          </section>

          <section className="glass-card-heavy p-6 relative overflow-hidden">
             <div className="absolute top-0 right-0 p-4 opacity-5">
                <Shield className="h-24 w-24" />
             </div>
            <div className="flex items-center gap-2 mb-4">
              <Shield className="h-4 w-4 text-emerald-400" />
              <h3 className="text-sm font-black text-[var(--text-primary)] uppercase tracking-widest">Sistema y Capas</h3>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--bg-border)]">
                <span className="text-[10px] font-black uppercase text-[var(--text-muted)] tracking-widest">Infraestructura</span>
                <span className="text-[10px] font-black text-[var(--text-primary)] bg-[var(--bg-hover)] px-2 py-0.5 rounded">{status?.provider ?? 'Ollama Local'}</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--bg-border)]">
                <span className="text-[10px] font-black uppercase text-[var(--text-muted)] tracking-widest">Estado Cuant</span>
                <span className="text-[10px] font-black text-emerald-400">Verificado </span>
              </div>
              <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/10 text-[10px] leading-relaxed text-[var(--text-secondary)] italic">
                &quot;El copiloto está configurado para priorizar la preservación de capital y la identificación de sesgos cognitivos en la ejecución.&quot;
              </div>
            </div>
          </section>
        </aside>
      </div>
    </motion.div>
  )
}
