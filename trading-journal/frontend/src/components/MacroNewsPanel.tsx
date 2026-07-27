'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { 
  RefreshCw, Globe, AlertTriangle, TrendingUp, TrendingDown, 
  CalendarDays, Brain, ShieldAlert, Clock, Sparkles
} from 'lucide-react'
import { buildApiUrl } from '@/lib/api'
import BloombergSentinel, { type BloombergData } from './BloombergSentinel'

interface MacroNewsItem {
  id: number
  title: string
  content: string
  published_at: string
  source: string
  url?: string
  impact_score: number
  ai_interpretation: string
  ai_suggestion: string
}

// Event timeline types
interface EventItem {
  id: number
  scheduled_at: string
  title: string
  impact: string
  impact_score: number
  currency: string
  forecast?: string
  previous?: string
  actual?: string
}

interface MacroNewsPanelProps {
  onAskAi?: (seed: { focus: string; prompt: string }) => void
  accountLogin?: string  null
  serverName?: string  null
}

function parseApiDate(value: string): Date {
  const hasTimezone = /(?:Z[+-]\d{2}:?\d{2})$/i.test(value)
  return new Date(hasTimezone ? value : `${value}Z`)
}

export default function MacroNewsPanel({ onAskAi, accountLogin, serverName }: MacroNewsPanelProps) {
  const [news, setNews] = useState<MacroNewsItem[]>([])
  const [bloombergData, setBloombergData] = useState<BloombergData  undefined>(undefined)
  const [loading, setLoading] = useState(true)
  const [localEvents, setLocalEvents] = useState<EventItem[]>([])
  const [impactTab, setImpactTab] = useState<'relevant'  'low'>('relevant')

  const fetchNews = async () => {
    try {
      setLoading(true)
      const res = await fetch(buildApiUrl('/macro/news', { limit: 50 }))
      if (res.ok) {
        const data = await res.json()
        setNews(data)
      }
    } catch (e) {
      console.error('Failed to fetch macro news', e)
    } finally {
      setLoading(false)
    }
  }

  const fetchBloomberg = useCallback(async () => {
    try {
      const res = await fetch(buildApiUrl('/bloomberg/latest', {
        account_login: accountLogin,
        server_name: serverName,
      }))
      if (res.ok) {
        const data = await res.json()
        setBloombergData(data)
      }
    } catch (e) {
      console.error('Failed to fetch bloomberg status', e)
    }
  }, [accountLogin, serverName])

  const fetchEvents = async () => {
    try {
      const res = await fetch(buildApiUrl('/macro/events', { days: 7 }))
      if (res.ok) {
        const data = await res.json()
        setLocalEvents(Array.isArray(data) ? data.filter((event: EventItem) => event.impact_score >= 6) : [])
      }
    } catch (e) {
      console.error('Failed to fetch economic calendar', e)
    }
  }

  const manualRefresh = async () => {
    try {
      setLoading(true)
      await fetch(buildApiUrl('/macro/refresh'), { method: 'POST' })
      await Promise.all([fetchNews(), fetchBloomberg(), fetchEvents()])
    } catch (e) {
      console.error('Manual refresh failed', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setBloombergData(undefined)
    fetchNews()
    fetchBloomberg()
    fetchEvents()

    /* Legacy mock calendar removed. Events now come from /macro/events.
    // Convert mock release times (standard Eastern Time) to local browser timezone
    const formatEventTime = (utcHour: number, utcMin: number, daysOffset = 0) => {
      const d = new Date()
      if (daysOffset === -1) {
        // Find next Thursday
        const day = d.getDay()
        const diff = (4 + 7 - day) % 7  7
        d.setDate(d.getDate() + diff)
      } else {
        d.setDate(d.getDate() + daysOffset)
      }
      
      const utcDate = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate(), utcHour, utcMin, 0))
      return utcDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
    }

    setLocalEvents([
      { time: formatEventTime(12, 30, 0), date: 'HOY', title: 'IPC Subyacente m/m', impact: 'HIGH', currency: 'USD' },
      { time: formatEventTime(18, 0, 1), date: 'MAÑANA', title: 'Discurso de Miembro del FOMC', impact: 'MEDIUM', currency: 'USD' },
      { time: formatEventTime(12, 30, -1), date: 'JUEVES', title: 'Peticiones de Subsidio por Desempleo', impact: 'HIGH', currency: 'USD' },
    ]) */

    const interval = setInterval(() => {
      fetchNews()
      fetchBloomberg()
      fetchEvents()
    }, 60 * 1000)
    return () => clearInterval(interval)
  }, [accountLogin, serverName, fetchBloomberg])

  // Derive market regime from Bloomberg/HMM data dynamically
  const stressProb = bloombergData?.stress_prob ?? 0.30
  const dominantTheme = bloombergData?.dominant_theme ?? 'Neutral'
  
  const getVolatilityLabel = (stress: number) => {
    if (stress > 0.6) return 'ALTA'
    if (stress > 0.3) return 'MODERADA'
    return 'BAJA'
  }

  const getVolatilityClass = (stress: number) => {
    if (stress > 0.6) return 'text-[var(--c-negative)] text-glow-red font-black'
    if (stress > 0.3) return 'text-[var(--c-warning)] text-glow-gold font-black'
    return 'text-[var(--c-positive)] text-glow-green font-black'
  }

  const getLiquidityLabel = (stress: number) => {
    if (stress > 0.7) return 'ILÍQUIDO'
    if (stress > 0.4) return 'RESTRINGIDA'
    return 'ÓPTIMA'
  }

  const getLiquidityClass = (stress: number) => {
    if (stress > 0.7) return 'text-[var(--c-negative)] font-black'
    if (stress > 0.4) return 'text-[var(--c-warning)] font-black'
    return 'text-[var(--c-positive)] font-black'
  }

  const getDirectionLabel = (theme: string, stress: number) => {
    if (stress > 0.65) return 'EXTREMA INCERTIDUMBRE'
    if (theme.toLowerCase().includes('bull')  theme.toLowerCase().includes('compra')  theme.toLowerCase().includes('risk on')) {
      return 'ALCISTA'
    }
    if (theme.toLowerCase().includes('bear')  theme.toLowerCase().includes('venta')  theme.toLowerCase().includes('risk off')) {
      return 'BAJISTA'
    }
    return 'LATERAL / RANGOS'
  }

  const getDirectionClass = (theme: string, stress: number) => {
    if (stress > 0.65) return 'text-[var(--c-negative)] font-black'
    const dir = getDirectionLabel(theme, stress)
    if (dir === 'ALCISTA') return 'text-[var(--c-positive)] font-black'
    if (dir === 'BAJISTA') return 'text-[var(--c-negative)] font-black'
    return 'text-[var(--text-primary)] font-black'
  }

  const getTacticalRecommendation = (theme: string, stress: number) => {
    if (stress > 0.6) {
      return 'Reducir tamaño de posición a la mitad. Priorizar coberturas y arbitraje. Evitar operaciones de continuidad (breakouts).'
    }
    if (theme.toLowerCase().includes('bull')  theme.toLowerCase().includes('risk on')) {
      return 'Sesgo comprador activo. Buscar retrocesos ordenados en soportes H4. Priorizar breakouts confirmados por volumen.'
    }
    if (theme.toLowerCase().includes('bear')  theme.toLowerCase().includes('risk off')) {
      return 'Sesgo vendedor activo. Buscar ventas en rebotes a medias móviles rápidas. Minimizar exposición a renta variable.'
    }
    return 'Rango establecido. Priorizar estrategias de reversión a la media (Mean-Reversion) en extremos de valor del perfil de volumen.'
  }

  const globalSentiment = stressProb > 0.5 ? 'RISK OFF' : stressProb > 0.35 ? 'NEUTRAL' : 'RISK ON'
  const relevantNews = news.filter((item) => item.impact_score >= 6)
  const lowImpactNews = news.filter((item) => item.impact_score <= 5)
  const visibleNews = impactTab === 'relevant' ? relevantNews : lowImpactNews
  const nextEvent = localEvents.find((event) => parseApiDate(event.scheduled_at).getTime() >= Date.now()) ?? localEvents[0]
  const highImpactEvents = localEvents.filter((event) => event.impact === 'HIGH').length

  const eventDateLabel = (value: string) => {
    const date = parseApiDate(value)
    const today = new Date()
    const tomorrow = new Date(today)
    tomorrow.setDate(today.getDate() + 1)
    if (date.toDateString() === today.toDateString()) return 'HOY'
    if (date.toDateString() === tomorrow.toDateString()) return 'MAÑANA'
    return date.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric' }).toUpperCase()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-6 max-w-[1440px] mx-auto text-[var(--text-primary)]"
    >
      {/* 1. HEADER & SENTIMENT STRIP */}
      <div className="widget overflow-hidden relative group">
        {/* Shimmer top decoration */}
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[var(--c-neutral)] via-[var(--c-accent)] to-[var(--c-neutral)] opacity-50" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between p-6 gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Globe className="w-5 h-5 text-[var(--c-neutral)]" />
              <h3 className="text-base font-black tracking-tighter uppercase italic text-[var(--text-primary)]">
                Macro Intel
              </h3>
            </div>
            <p className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-widest mt-1">
              Contexto Global y Motor de Noticias
            </p>
          </div>
          
          <div className="flex gap-2">
            <button 
              type="button"
              onClick={() => onAskAi?.({
                focus: 'Macro Intel',
                prompt: 'Analiza el estado actual del Bloomberg Sentinel, los indicadores cuantitativos de régimen (HMM) y las últimas noticias macro. ¿Cuáles son las implicaciones tácticas y los riesgos principales para nuestra operativa?'
              })}
              className="h-10 px-6 bg-purple-600 hover:bg-purple-500 text-white transition-all rounded-xl font-black uppercase text-[10px] tracking-widest flex items-center gap-2 shadow-[0_8px_20px_rgba(139,92,246,0.25)]"
            >
              <Brain className="w-3.5 h-3.5" />
              CONSULTAR IA
            </button>
            <button 
              onClick={manualRefresh} 
              disabled={loading}
              className="btn btn-primary gap-2"
            >
              <RefreshCw className={clsx('w-3.5 h-3.5', loading && 'animate-spin')} />
              FORZAR SINCRONIZACIÓN
            </button>
          </div>
        </div>
        
        {/* Dynamic Sentiment Strip */}
        <div className={clsx(
          "w-full flex items-center justify-center gap-3 py-3 border-t border-[var(--bg-border)]",
          globalSentiment === 'RISK ON' ? "bg-[var(--c-positive-dim)]" : 
          globalSentiment === 'RISK OFF' ? "bg-[var(--c-negative-dim)]" : 
          "bg-[var(--bg-surface)]"
        )}>
          <span className={clsx(
            "w-2 h-2 rounded-full",
            globalSentiment === 'RISK ON' ? "bg-[var(--c-positive)] shadow-[0_0_8px_var(--c-positive)]" : 
            globalSentiment === 'RISK OFF' ? "bg-[var(--c-negative)] shadow-[0_0_8px_var(--c-negative)]" : 
            "bg-[var(--c-warning)]"
          )} />
          <span className={clsx(
            "text-xs font-black uppercase tracking-[0.25em] font-data",
            globalSentiment === 'RISK ON' ? "text-[var(--c-positive)]" : 
            globalSentiment === 'RISK OFF' ? "text-[var(--c-negative)]" : 
            "text-[var(--c-warning)]"
          )}>
            SENTIMIENTO GLOBAL: {globalSentiment}
          </span>
        </div>
      </div>

      {/* BLOOMBERG SENTINEL INTEGRATION */}
      <section className="w-full">
        <BloombergSentinel data={bloombergData} accountLogin={accountLogin} serverName={serverName} />
      </section>

      {/* 2. CORE DATA: REGIME & TIMELINE */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* MARKET REGIME (Left - 5 columns) */}
        <div className="lg:col-span-5 widget overflow-hidden">
          <div className="p-5">
            <div className="flex items-center justify-between gap-3 mb-5 border-b border-[var(--bg-border)] pb-4">
              <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-[var(--c-neutral)]" />
              <h3 className="text-xs font-black uppercase tracking-[0.15em] text-[var(--text-secondary)]">Régimen de Mercado</h3>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--bg-border)] bg-[var(--bg-void)] px-2.5 py-1 text-[9px] font-black uppercase tracking-wider text-[var(--text-muted)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--c-positive)] shadow-[0_0_8px_var(--c-positive)]" />
                En vivo
              </span>
            </div>

            <div className="rounded-2xl border border-[var(--bg-border)] bg-gradient-to-br from-[var(--bg-void)] to-[var(--bg-surface)] p-4 mb-4">
              <div className="flex items-end justify-between gap-4 mb-3">
                <div>
                  <p className="text-[9px] uppercase font-black tracking-[0.18em] text-[var(--text-muted)]">Nivel de estrés de mercado</p>
                  <p className="mt-1 font-data text-2xl font-black text-[var(--text-primary)]">{Math.round(stressProb * 100)}%</p>
                </div>
                <span className={clsx("text-[10px] font-black uppercase tracking-wider", getVolatilityClass(stressProb))}>
                  {getVolatilityLabel(stressProb)}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bg-border)]">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all duration-700',
                    stressProb > 0.6 ? 'bg-[var(--c-negative)]' : stressProb > 0.3 ? 'bg-[var(--c-warning)]' : 'bg-[var(--c-positive)]'
                  )}
                  style={{ width: `${Math.max(4, Math.round(stressProb * 100))}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="bg-[var(--bg-void)] p-3.5 rounded-xl border border-[var(--bg-border)] hover:border-[var(--bg-border-strong)] transition-all">
                <p className="text-[9px] uppercase font-bold tracking-wider text-[var(--text-muted)] mb-1">Volatilidad</p>
                <p className={clsx("text-xs font-black uppercase tracking-wide", getVolatilityClass(stressProb))}>
                  {getVolatilityLabel(stressProb)}
                </p>
              </div>
              
              <div className="bg-[var(--bg-void)] p-3.5 rounded-xl border border-[var(--bg-border)] hover:border-[var(--bg-border-strong)] transition-all">
                <p className="text-[9px] uppercase font-bold tracking-wider text-[var(--text-muted)] mb-1">Liquidez</p>
                <p className={clsx("text-xs font-black uppercase tracking-wide", getLiquidityClass(stressProb))}>
                  {getLiquidityLabel(stressProb)}
                </p>
              </div>
              
              <div className="bg-[var(--bg-void)] p-3.5 rounded-xl border border-[var(--bg-border)] hover:border-[var(--bg-border-strong)] transition-all">
                <p className="text-[9px] uppercase font-bold tracking-wider text-[var(--text-muted)] mb-1">Dirección</p>
                <p className={clsx("text-xs font-black uppercase tracking-wide", getDirectionClass(dominantTheme, stressProb))}>
                  {getDirectionLabel(dominantTheme, stressProb)}
                </p>
              </div>
            </div>
          </div>

          <div className="border-t border-[var(--bg-border)] bg-[linear-gradient(135deg,rgba(59,130,246,0.10),transparent)] p-5">
            <p className="text-[10px] uppercase font-black tracking-[0.14em] text-[var(--c-neutral)] mb-2 flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5" /> Recomendación táctica
            </p>
            <p className="text-[12px] leading-5 font-semibold text-[var(--text-secondary)]">
              {getTacticalRecommendation(dominantTheme, stressProb)}
            </p>
          </div>
        </div>

        {/* EVENT TIMELINE (Right - 7 columns) */}
        <div className="lg:col-span-7 widget overflow-hidden">
          <div className="flex flex-col gap-4 border-b border-[var(--bg-border)] p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <CalendarDays className="w-4 h-4 text-[var(--c-warning)]" />
              <div>
                <h3 className="text-xs font-black uppercase tracking-[0.15em] text-[var(--text-secondary)]">Horizonte de Eventos</h3>
                <p className="mt-1 text-[9px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Calendario macro de relevancia operativa</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)] px-2.5 py-1.5 text-[9px] font-black uppercase tracking-wider text-[var(--text-muted)]">
                {localEvents.length} eventos
              </span>
              <span className="rounded-lg border border-[rgba(244,63,94,0.2)] bg-[var(--c-negative-dim)] px-2.5 py-1.5 text-[9px] font-black uppercase tracking-wider text-[var(--c-negative)]">
                {highImpactEvents} críticos
              </span>
            </div>
          </div>

          {nextEvent && (
            <div className="mx-5 mt-5 flex items-center justify-between gap-4 rounded-xl border border-[rgba(59,130,246,0.24)] bg-[linear-gradient(100deg,rgba(59,130,246,0.12),rgba(59,130,246,0.02))] p-3.5">
              <div className="min-w-0">
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-[var(--c-neutral)]">Próximo catalizador</p>
                <p className="mt-1 truncate text-xs font-black text-[var(--text-primary)]">{nextEvent.title}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-[9px] font-bold uppercase text-[var(--text-muted)]">{eventDateLabel(nextEvent.scheduled_at)}</p>
                <p className="font-data text-sm font-black text-[var(--text-primary)]">
                  {parseApiDate(nextEvent.scheduled_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          )}

          <div className="m-5 max-h-[540px] space-y-2 overflow-y-auto pr-1 custom-scrollbar">
            {localEvents.length > 0 ? (
              localEvents.map((evt, idx) => (
                <div key={evt.id ?? idx} className="group flex items-center gap-3 rounded-xl border border-[var(--bg-border)] bg-[var(--bg-void)] p-3 transition-all hover:-translate-y-px hover:border-[var(--bg-border-strong)] hover:bg-[var(--bg-hover)]">
                  <div className="flex min-w-[62px] flex-col items-center justify-center border-r border-[var(--bg-border-strong)] pr-3">
                    <span className="text-[9px] uppercase font-black tracking-wider text-[var(--text-muted)]">{eventDateLabel(evt.scheduled_at)}</span>
                    <span className="text-xs font-data font-black text-[var(--text-primary)] mt-0.5">
                      {parseApiDate(evt.scheduled_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className={clsx(
                        "text-[9px] font-black uppercase px-2 py-0.5 rounded border",
                        evt.impact === 'HIGH' ? "bg-[var(--c-negative-dim)] text-[var(--c-negative)] border-[rgba(244,63,94,0.2)]" : 
                        evt.impact === 'MEDIUM' ? "bg-[var(--c-warning-dim)] text-[var(--c-warning)] border-[rgba(234,179,8,0.2)]" :
                        "bg-[var(--bg-surface)] text-[var(--text-muted)] border-[var(--bg-border)]"
                      )}>
                        {evt.impact === 'HIGH' ? 'ALTO' : evt.impact === 'MEDIUM' ? 'MEDIO' : 'BAJO'}
                      </span>
                      <span className="text-[9px] font-black uppercase bg-[var(--bg-surface)] border border-[var(--bg-border)] text-[var(--text-primary)] px-2 py-0.5 rounded">
                        {evt.currency}
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[var(--text-primary)] transition-colors group-hover:text-white">{evt.title}</p>
                    {(evt.actual  evt.forecast  evt.previous) && (
                      <p className="mt-1 text-[9px] font-data text-[var(--text-muted)]">
                        Actual {evt.actual  'N/D'} · Prev. {evt.forecast  'N/D'} · Anterior {evt.previous  'N/D'}
                      </p>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-[var(--text-muted)]">
                <Clock className="w-8 h-8 mb-2 opacity-20" />
                <p className="text-xs font-bold uppercase tracking-widest">Sin eventos de alto impacto en las próximas 24h</p>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 3. DETAILS: AI INTERPRETATION FEED */}
      <section className="widget overflow-hidden">
        <div className="px-5 py-4 border-b border-[var(--bg-border)] flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between bg-gradient-to-r from-[var(--bg-void)] to-transparent">
          <div className="flex items-center gap-2">
            <Brain className="w-4.5 h-4.5 text-[var(--c-info)]" />
            <h3 className="text-xs font-black uppercase tracking-[0.15em] text-[var(--text-primary)]">Interpretación de IA en Tiempo Real</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="period-tabs">
              <button className={clsx('period-tab', impactTab === 'relevant' && 'active')} onClick={() => setImpactTab('relevant')}>
                Alto y medio ({relevantNews.length})
              </button>
              <button className={clsx('period-tab', impactTab === 'low' && 'active')} onClick={() => setImpactTab('low')}>
                Bajo impacto ({lowImpactNews.length})
              </button>
            </div>
            <span className="text-[9px] px-2 py-0.5 bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-full text-[var(--text-muted)] font-black uppercase tracking-wider">
              Actualización 60s
            </span>
          </div>
        </div>

        <div className="divide-y divide-[var(--bg-border)] bg-[var(--bg-elevated)]">
          {loading && news.length === 0 ? (
            <div className="p-12 text-center">
              <RefreshCw className="w-6 h-6 text-[var(--text-muted)] animate-spin mx-auto mb-3" />
              <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest">Sincronizando flujo de IA...</p>
            </div>
          ) : visibleNews.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest">No hay noticias en esta categoría.</p>
            </div>
          ) : (
            <AnimatePresence>
              {visibleNews.map((item, index) => {
                const isPositive = item.ai_suggestion.toLowerCase().match(/longcompraalcista/);
                const isNegative = item.ai_suggestion.toLowerCase().match(/shortventabajista/);
                
                return (
                  <motion.div 
                    key={item.id} 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="p-5 hover:bg-[var(--bg-hover)] transition-colors"
                  >
                    <div className="flex flex-col xl:flex-row xl:items-start gap-5">
                      {/* Header Info */}
                      <div className="xl:w-72 shrink-0">
                        <div className="flex items-center gap-2 mb-2.5">
                          <span className={clsx(
                            'px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border',
                            item.impact_score >= 9 ? 'bg-[var(--c-negative-dim)] text-[var(--c-negative)] border-[var(--bg-border-strong)]' :
                            item.impact_score >= 7 ? 'bg-[var(--c-warning-dim)] text-[var(--c-warning)] border-[var(--bg-border-strong)]' :
                            'bg-[var(--bg-surface)] text-[var(--text-muted)] border-[var(--bg-border)]'
                          )}>
                            Impacto {item.impact_score}/10
                          </span>
                          <span className="text-[10px] font-data text-[var(--text-muted)]">
                            {parseApiDate(item.published_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <h4 className="text-sm font-black text-[var(--text-primary)] leading-snug mb-1.5">{item.title}</h4>
                        <p className="text-[9px] uppercase font-black text-[var(--text-muted)] tracking-widest">{item.source}</p>
                      </div>

                      {/* AI Analysis */}
                      <div className="flex-1 bg-[var(--bg-void)] p-4 rounded-xl border border-[var(--bg-border)] relative overflow-hidden group/chat">
                        <div className="absolute top-0 left-0 bottom-0 w-[3px] bg-[var(--c-info)]" />
                        
                        <div className="flex items-center gap-1.5 mb-2 pl-1">
                          <Sparkles className="w-3.5 h-3.5 text-[var(--c-info)]" />
                          <span className="text-[9px] font-black uppercase tracking-[0.15em] text-[var(--c-info)]">Consenso AI Mentor</span>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-4 pl-1">
                          {item.ai_interpretation}
                        </p>
                        
                        {/* Suggestion Tag & AI Button */}
                        <div className="flex items-center justify-between mt-4">
                          <div className={clsx(
                            "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border",
                            isPositive ? "bg-[var(--c-positive-dim)] text-[var(--c-positive)]" : 
                            isNegative ? "bg-[var(--c-negative-dim)] text-[var(--c-negative)]" : 
                            "bg-[var(--c-warning-dim)] text-[var(--c-warning)]"
                          )}
                          style={{
                            borderColor: isPositive ? 'rgba(16, 185, 129, 0.2)' : 
                                         isNegative ? 'rgba(244, 63, 94, 0.2)' : 
                                         'rgba(234, 179, 8, 0.2)'
                          }}>
                            {isPositive ? <TrendingUp className="w-3.5 h-3.5" /> : 
                             isNegative ? <TrendingDown className="w-3.5 h-3.5" /> : 
                             <AlertTriangle className="w-3.5 h-3.5" />}
                            <span className="text-[9px] font-black uppercase tracking-[0.1em] font-data">
                              {item.ai_suggestion}
                            </span>
                          </div>

                          <button
                            type="button"
                            onClick={() => onAskAi?.({
                              focus: 'Macro Intel',
                              prompt: `Analiza la noticia "${item.title}" (${item.source}). Su impacto es de ${item.impact_score}/10. Interpretación de la IA: ${item.ai_interpretation}. Sugerencia: ${item.ai_suggestion}. ¿Qué repercusiones específicas tiene esta noticia en la gestión de mi portafolio y nivel de riesgo?`
                            })}
                            className="h-7 px-3 bg-purple-600/10 hover:bg-purple-600/25 border border-purple-500/20 hover:border-purple-500/40 text-purple-400 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all"
                          >
                            <Brain className="w-3.5 h-3.5" />
                            Consultar IA
                          </button>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          )}
        </div>
      </section>
    </motion.div>
  )
}
