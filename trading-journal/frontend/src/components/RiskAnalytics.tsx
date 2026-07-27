'use client'

import { motion } from 'framer-motion'
import {
  Activity,
  FlaskConical,
  Gauge,
  GitBranch,
  Shield,
  Sigma,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { AiIntent } from '@/lib/ai'

interface QuantData {
  skewness: number
  kurtosis: number
  jarque_bera_stat: number
  jarque_bera_pvalue: number
  is_normal: boolean
  psr: number
  significance: string
  runs_zscore: number
  serial_independent: boolean
  hmm_regime?: string
  mc_dd_p10: number
  mc_dd_p1: number
  prob_ruin_10pct: number
  prob_ruin_20pct: number
  e_ratio: number  null
  commission_drag_pct: number
}

interface RiskData {
  var: number
  cvar: number
  cf_var: number
  garch_var: number
  vol_regime: string
  avg_risk: number
  max_risk: number
}

interface PerfData {
  calmar: number
  recovery_factor: number
  tail_ratio: number
  win_rate: number
  pf: number
  optimal_risk_kelly: number
  suggested_risk_half_kelly: number
}

interface Props {
  quant: QuantData
  risk: RiskData
  perf: PerfData
  returns?: number[]
  onAskAi?: (intent: AiIntent) => void
}

function sanitize(value: number  null  undefined, fallback = 0): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function calculateBlackKnightScore(quant: QuantData, perf: PerfData): number {
  const pf = sanitize(perf.pf, 0)
  const pfScore = clamp((pf - 1) / 1, 0, 1) * 25

  const ruinProb = sanitize(quant.prob_ruin_10pct, 0)
  const ruinScore = Math.max(1 - ruinProb / 0.1, 0) * 15

  const drawdownVal = Math.abs(sanitize(quant.mc_dd_p10, 0))
  const drawdownScore = Math.max(1 - drawdownVal / 0.2, 0) * 15

  const psr = sanitize(quant.psr, 0)
  const psrScore = clamp((psr - 0.5) / 0.45, 0, 1) * 25

  const z = Math.abs(sanitize(quant.runs_zscore, 0))
  const independenceScore = Math.max(1 - z / 1.96, 0) * 20

  const total = pfScore + ruinScore + drawdownScore + psrScore + independenceScore
  return Math.round(clamp(total, 0, 100))
}

function SectionCard({
  icon: Icon,
  title,
  subtitle,
  accentClass,
  className,
  children,
}: {
  icon: LucideIcon
  title: string
  subtitle: string
  accentClass?: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <section
      className={clsx(
        'glass-card p-4 md:p-5',
        'bg-[linear-gradient(160deg,rgba(255,255,255,0.025),rgba(255,255,255,0)_55%)]',
        className,
      )}
    >
      <header className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className={clsx(
              'h-8 w-8 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] grid place-items-center shrink-0',
              accentClass,
            )}
          >
            <Icon className="h-4 w-4 text-[var(--c-warning)]" />
          </span>
          <div className="min-w-0">
            <h3 className="text-sm font-bold text-[var(--text-primary)] truncate">{title}</h3>
            <p className="text-[11px] text-[var(--text-muted)] mt-0.5 truncate">{subtitle}</p>
          </div>
        </div>
      </header>
      {children}
    </section>
  )
}

function MetricLine({
  label,
  value,
  subValue,
  tone,
}: {
  label: string
  value: string
  subValue?: string
  tone?: 'good'  'warn'  'bad'  'neutral'
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[var(--bg-border)] last:border-b-0">
      <div className="flex flex-col">
        <p className="text-[11px] text-[var(--text-secondary)]">{label}</p>
        {subValue && <p className="text-[9px] text-[var(--text-muted)] font-data">{subValue}</p>}
      </div>
      <span
        className={clsx(
          'font-data text-sm font-bold',
          tone === 'good' && 'text-[var(--c-positive)]',
          tone === 'warn' && 'text-[var(--c-warning)]',
          tone === 'bad' && 'text-[var(--c-negative)]',
          (!tone  tone === 'neutral') && 'text-[var(--text-primary)]',
        )}
      >
        {value}
      </span>
    </div>
  )
}

function RiskBar({
  label,
  value,
  cap,
  color,
}: {
  label: string
  value: number
  cap: number
  color: string
}) {
  const pct = clamp((Math.abs(value) / cap) * 100, 0, 100)
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-[0.12em] font-bold text-[var(--text-muted)]">{label}</p>
        <p className="font-data text-xs font-bold text-[var(--text-primary)]">{(value * 100).toFixed(2)}%</p>
      </div>
      <div className="h-1.5 rounded-full bg-[var(--bg-border)] overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
    </div>
  )
}

type ReturnDistributionPoint = {
  x0: number
  x1: number
  center: number
  count: number
  normal: number
}

type ReturnDistribution = {
  bins: ReturnDistributionPoint[]
  normalCurve: Array<{ x: number; y: number }>
  mean: number
  sigma: number
  sampleSize: number
}

function buildReturnDistribution(values: number[]): ReturnDistribution  null {
  const clean = values.filter((v) => Number.isFinite(v))
  if (clean.length < 6) return null

  const n = clean.length
  const mean = clean.reduce((acc, v) => acc + v, 0) / n
  const variance = clean.reduce((acc, v) => acc + (v - mean) ** 2, 0) / Math.max(1, n - 1)
  const sigma = Math.sqrt(variance)
  if (!Number.isFinite(sigma)  sigma <= 0) return null

  let min = Math.min(...clean)
  let max = Math.max(...clean)
  if (min === max) {
    min -= Math.max(Math.abs(min) * 0.1, 0.001)
    max += Math.max(Math.abs(max) * 0.1, 0.001)
  }

  const bins = Math.min(14, Math.max(8, Math.round(Math.sqrt(n) * 1.8)))
  const width = (max - min) / bins
  const counts = Array.from({ length: bins }, () => 0)

  for (const v of clean) {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / width)))
    counts[idx] += 1
  }

  const histogram = counts.map((count, idx) => {
    const x0 = min + idx * width
    const x1 = x0 + width
    const center = x0 + width / 2
    const z = (center - mean) / sigma
    const pdf = Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI))
    const normal = pdf * n * width
    return { x0, x1, center, count, normal }
  })

  const curveMin = Math.min(min, mean - 3 * sigma)
  const curveMax = Math.max(max, mean + 3 * sigma)
  const curveRange = Math.max(curveMax - curveMin, 0.000001)
  const normalCurve = Array.from({ length: 72 }, (_, idx) => {
    const x = curveMin + (curveRange * idx) / 71
    const z = (x - mean) / sigma
    const pdf = Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI))
    return { x, y: pdf * n * width }
  })

  return { bins: histogram, normalCurve, mean, sigma, sampleSize: n }
}

export default function RiskAnalytics({ quant, risk, perf, returns = [] , onAskAi }: Props) {
  const bkScore = calculateBlackKnightScore(quant, perf)

  const skewness = sanitize(quant.skewness)
  const kurtosis = sanitize(quant.kurtosis)
  const jb = sanitize(quant.jarque_bera_stat)
  const jbP = sanitize(quant.jarque_bera_pvalue)
  const psr = sanitize(quant.psr)
  const runsZ = sanitize(quant.runs_zscore)
  const mcP10 = Math.abs(sanitize(quant.mc_dd_p10))
  const mcP1 = Math.abs(sanitize(quant.mc_dd_p1))
  const ruin10 = sanitize(quant.prob_ruin_10pct)
  const ruin20 = sanitize(quant.prob_ruin_20pct)
  const eRatio = quant.e_ratio
  const commissionDrag = sanitize(quant.commission_drag_pct)

  const var99 = sanitize(risk.var)
  const cvar = sanitize(risk.cvar)
  const cfVar = sanitize(risk.cf_var)
  const garch = sanitize(risk.garch_var)

  const winRate = sanitize(perf.win_rate)
  const pf = sanitize(perf.pf)
  const calmar = sanitize(perf.calmar)
  const recovery = sanitize(perf.recovery_factor)
  const tailRatio = sanitize(perf.tail_ratio)
  const kelly = sanitize(perf.optimal_risk_kelly)
  const halfKelly = sanitize(perf.suggested_risk_half_kelly)

  const psrPct = clamp(psr * 100, 0, 100)
  const pressureComposite = (clamp(cvar / 0.09, 0, 1) + clamp(ruin10 / 0.15, 0, 1) + clamp(mcP10 / 0.16, 0, 1)) / 3
  const pressureLabel = pressureComposite < 0.33 ? 'Contained' : pressureComposite < 0.66 ? 'Elevated' : 'Critical'
  const pressureTone = pressureComposite < 0.33 ? 'text-[var(--c-positive)]' : pressureComposite < 0.66 ? 'text-[var(--c-warning)]' : 'text-[var(--c-negative)]'

  const normalityTag = quant.is_normal ? 'Stable distribution' : 'Fat-tail caution'
  const serialTag = quant.serial_independent ? 'Pattern stability' : 'Clustered outcomes'
  const regimeTag = Math.abs(runsZ) <= 1.96 ? 'Balanced regime' : runsZ < -1.96 ? 'Momentum regime' : 'Mean reversion'

  const scoreAngle = clamp(bkScore * 3.6, 0, 360)
  const returnDistribution = buildReturnDistribution(returns)
  const hasDistribution = Boolean(returnDistribution)
  const maxDistributionY = hasDistribution
    ? Math.max(
        1,
        ...returnDistribution.bins.flatMap((p) => [p.count, p.normal]),
        ...returnDistribution.normalCurve.map((p) => p.y),
      )
    : 1
  const distributionMinX = hasDistribution
    ? Math.min(...returnDistribution.bins.map((p) => p.x0), ...returnDistribution.normalCurve.map((p) => p.x))
    : 0
  const distributionMaxX = hasDistribution
    ? Math.max(...returnDistribution.bins.map((p) => p.x1), ...returnDistribution.normalCurve.map((p) => p.x))
    : 1
  const distributionRangeX = Math.max(distributionMaxX - distributionMinX, 0.000001)

  const riskInsightPrompt =
    `Analiza el perfil de riesgo actual de la cartera con foco en ${pressureLabel}. ` +
    `BK Score ${bkScore}, PSR ${psrPct.toFixed(1)}%, Calmar ${calmar.toFixed(2)}, PF ${pf.toFixed(2)}, ` +
    `VaR ${(var99 * 100).toFixed(2)}%, CVaR ${(cvar * 100).toFixed(2)}%, CF-VaR ${(cfVar * 100).toFixed(2)}%, ` +
    `GARCH ${(garch * 100).toFixed(2)}%, tail ratio ${tailRatio.toFixed(2)}, commission drag ${(commissionDrag * 100).toFixed(3)}%. ` +
    `Devuelve diagnostico, 3 observaciones clave y 3 acciones inmediatas.`

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      <section className="glass-card p-5 md:p-6 relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0 opacity-45"
          style={{
            background:
              'radial-gradient(75% 120% at 0% 0%, rgba(214,174,108,0.22) 0%, rgba(214,174,108,0.0) 55%), radial-gradient(65% 100% at 100% 0%, rgba(75,163,199,0.20) 0%, rgba(75,163,199,0.0) 58%)',
          }}
        />
        <div className="relative grid grid-cols-1 lg:grid-cols-[1.45fr_1fr] gap-5 items-center">
          <div>
            <p className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--c-warning)]">Premium Risk Suite</p>
            <h2 className="text-xl md:text-2xl font-black text-[var(--text-primary)] mt-1 tracking-tight">Capital Safety & Performance Clarity</h2>
            <p className="text-[12px] text-[var(--text-secondary)] mt-2 max-w-2xl">
              Elegant, decision-ready view of stability, drawdown exposure and execution quality for premium retail clients.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2.5 py-1 text-[10px] uppercase tracking-[0.1em] text-[var(--text-secondary)]">
                {normalityTag}
              </span>
              <span className="rounded-full border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2.5 py-1 text-[10px] uppercase tracking-[0.1em] text-[var(--text-secondary)]">
                {serialTag}
              </span>
              <span className="rounded-full border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2.5 py-1 text-[10px] uppercase tracking-[0.1em] text-[var(--text-secondary)]">
                {regimeTag}
              </span>
              <span className="rounded-full border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2.5 py-1 text-[10px] uppercase tracking-[0.1em] text-[var(--text-secondary)]">
                Confidence: {quant.significance  'N/A'}
              </span>
              {onAskAi && (
                <button
                  type="button"
                  onClick={() => onAskAi({ focus: 'Riesgo y Proteccion', prompt: riskInsightPrompt })}
                  className="inline-flex items-center gap-1 rounded-full border border-[rgba(234,179,8,0.25)] bg-[rgba(214,174,108,0.12)] px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-[var(--c-warning)] transition-colors hover:bg-[rgba(214,174,108,0.18)]"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Generar insight IA
                </button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-[auto_1fr] gap-4 items-center">
            <div
              className="h-24 w-24 rounded-full p-1"
              style={{
                background: `conic-gradient(var(--c-info) ${scoreAngle}deg, rgba(255,255,255,0.08) ${scoreAngle}deg)`,
              }}
            >
              <div className="h-full w-full rounded-full bg-[var(--bg-base)] border border-[var(--bg-border)] grid place-items-center">
                <div className="text-center">
                  <p className="font-data text-2xl font-black text-[var(--text-primary)] leading-none">{bkScore}</p>
                  <p className="text-[9px] uppercase tracking-[0.14em] text-[var(--text-muted)] mt-1">BK Score</p>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Risk Pressure</p>
                <p className={clsx('text-sm font-black mt-0.5', pressureTone)}>{pressureLabel}</p>
              </div>
              <div className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Edge Confidence</p>
                <p className="font-data text-sm font-bold text-[var(--text-primary)] mt-0.5">{psrPct.toFixed(1)}%</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <SectionCard
          icon={Sigma}
          title="Perfil de estabilidad"
          subtitle="Salud de distribucion y confianza estadistica"
          accentClass="bg-[rgba(214,174,108,0.08)]"
          className="xl:col-span-5"
        >
          <MetricLine label="Skewness" value={skewness.toFixed(4)} tone={Math.abs(skewness) < 0.5 ? 'good' : 'warn'} />
          <MetricLine label="Excess Kurtosis" value={kurtosis.toFixed(4)} tone={Math.abs(kurtosis) < 1.5 ? 'good' : 'warn'} />
          <MetricLine label="Jarque-Bera" value={jb.toFixed(2)} tone={jb < 6 ? 'good' : 'warn'} />
          <MetricLine
            label="JB p-value"
            value={jbP.toFixed(4)}
            tone={jbP >= 0.05 ? 'good' : 'warn'}
          />
          <MetricLine
            label="Probabilistic Sharpe Ratio"
            value={`${psrPct.toFixed(1)}%`}
            tone={psr >= 0.9 ? 'good' : psr >= 0.6 ? 'warn' : 'bad'}
          />

          <div className="mt-3 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-2.5">
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Distribucion de retornos diarios</p>
            {hasDistribution ? (
              <svg viewBox="0 0 320 120" className="w-full h-28 mt-2" role="img" aria-label="Histograma de retornos con curva normal">
                {returnDistribution.bins.map((p, idx) => {
                  const x = 20 + ((p.x0 - distributionMinX) / distributionRangeX) * 280
                  const barW = Math.max(1, ((p.x1 - p.x0) / distributionRangeX) * 280 - 2)
                  const h = (p.count / maxDistributionY) * 82
                  const y = 94 - h
                  return (
                    <rect
                      key={`bar-${idx}`}
                      x={x}
                      y={y}
                      width={Math.max(1, barW)}
                      height={h}
                      rx={1.5}
                      fill="var(--c-neutral-dim)"
                      stroke="var(--c-neutral)"
                      strokeOpacity="0.28"
                    />
                  )
                })}

                <path
                  d={returnDistribution.normalCurve
                    .map((p, idx) => {
                      const x = 20 + ((p.x - distributionMinX) / distributionRangeX) * 280
                      const y = 94 - (p.y / maxDistributionY) * 82
                      return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
                    })
                    .join(' ')}
                  fill="none"
                  stroke="var(--c-warning)"
                  strokeWidth="2"
                />

                <line x1="20" y1="94" x2="300" y2="94" stroke="var(--bg-border)" strokeDasharray="3 3" />
                <line x1="20" y1="12" x2="20" y2="94" stroke="var(--bg-border)" strokeDasharray="3 3" />
                <text x="20" y="112" fill="var(--text-muted)" fontSize="8" fontFamily="JetBrains Mono, monospace">
                  {(distributionMinX * 100).toFixed(2)}%
                </text>
                <text x="260" y="112" fill="var(--text-muted)" fontSize="8" fontFamily="JetBrains Mono, monospace">
                  {(distributionMaxX * 100).toFixed(2)}%
                </text>
              </svg>
            ) : (
              <p className="text-[11px] text-[var(--text-muted)] mt-2">Muestra insuficiente para estimar distribucion de retornos.</p>
            )}
            <p className="text-[11px] text-[var(--text-secondary)] mt-1">
              Barras: retorno diario observado. Linea dorada: normal teorica con la misma media y volatilidad.
            </p>
            {hasDistribution && (
              <p className="text-[10px] text-[var(--text-muted)] mt-1 font-data">
                N={returnDistribution.sampleSize}  media {(returnDistribution.mean * 100).toFixed(3)}%  sigma {(returnDistribution.sigma * 100).toFixed(3)}%
              </p>
            )}
          </div>
        </SectionCard>

        <SectionCard
          icon={Shield}
          title="Capital Protection"
          subtitle="Loss exposure from multiple risk models"
          accentClass="bg-[rgba(75,163,199,0.08)]"
          className="xl:col-span-4"
        >
          <div className="space-y-3">
            <RiskBar label="Historical VaR 99%" value={var99} cap={0.1} color="var(--c-negative)" />
            <RiskBar label="Historical CVaR 99%" value={cvar} cap={0.1} color="var(--c-warning)" />
            <RiskBar label="Cornish-Fisher VaR 99%" value={cfVar} cap={0.1} color="#B71C1C" />
            <RiskBar label="GARCH VaR 99%" value={garch} cap={0.1} color="var(--c-info)" />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2">
            <div className="rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2.5 py-2">
              <p className="text-[10px] text-[var(--text-muted)] uppercase">P(DD &gt; 10%)</p>
              <p className={clsx('font-data text-sm font-bold mt-0.5', ruin10 <= 0.05 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
                {(ruin10 * 100).toFixed(2)}%
              </p>
            </div>
            <div className="rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-2.5 py-2">
              <p className="text-[10px] text-[var(--text-muted)] uppercase">P(DD &gt; 20%)</p>
              <p className={clsx('font-data text-sm font-bold mt-0.5', ruin20 <= 0.03 ? 'text-[var(--c-positive)]' : 'text-[var(--c-negative)]')}>
                {(ruin20 * 100).toFixed(2)}%
              </p>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          icon={Gauge}
          title="Tamano de posicion"
          subtitle="Disciplina de asignacion y costo operativo"
          accentClass="bg-[rgba(214,174,108,0.08)]"
          className="xl:col-span-3"
        >
          <MetricLine label="Kelly Optimal" value={`${(kelly * 100).toFixed(2)}%`} tone="neutral" />
          <MetricLine label="Half-Kelly" value={`${(halfKelly * 100).toFixed(2)}%`} tone="good" />
          <MetricLine
            label="E-Ratio"
            value={eRatio === null  eRatio === undefined ? 'Insufficient data' : eRatio.toFixed(3)}
            tone={eRatio === null  eRatio === undefined ? 'warn' : eRatio > 1 ? 'good' : 'bad'}
          />
          <MetricLine
            label="Commission Drag"
            value={`${(commissionDrag * 100).toFixed(3)}%`}
            tone={commissionDrag <= 0.01 ? 'good' : 'warn'}
          />

          <div className="mt-3 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Guia de Tamano de Posicion</p>
            <p className="text-[12px] text-[var(--text-secondary)] mt-1">
              Keep position size near <span className="font-data font-bold text-[var(--text-primary)]">{(halfKelly * 100).toFixed(2)}%</span> per trade for smoother growth and lower stress.
            </p>
          </div>
        </SectionCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <SectionCard
          icon={FlaskConical}
          title="Escenarios de Estrés"
          subtitle="Proyecciones de drawdown"
          accentClass="bg-[rgba(75,163,199,0.08)]"
          className="xl:col-span-4"
        >
          <MetricLine
            label="Percentil 10 (Adverso)"
            value={`${(mcP10 * 100).toFixed(2)}%`}
            tone={mcP10 <= 0.1 ? 'good' : mcP10 <= 0.15 ? 'warn' : 'bad'}
          />
          <MetricLine
            label="Percentil 1 (Extremo)"
            value={`${(mcP1 * 100).toFixed(2)}%`}
            tone={mcP1 <= 0.2 ? 'warn' : 'bad'}
          />

          <div className="mt-3 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Interpretación</p>
            <p className="text-[12px] text-[var(--text-secondary)] mt-1">
              Este rango muestra qué tan profundos pueden ser los retrocesos en mercados difíciles y cuánta reserva es prudente mantener.
            </p>
          </div>
        </SectionCard>

        <SectionCard
          icon={GitBranch}
          title="Market Rhythm"
          subtitle="Behavior consistency and sequencing"
          accentClass="bg-[rgba(214,174,108,0.08)]"
          className="xl:col-span-4"
        >
          <MetricLine
            label="Independence (Runs Test)"
            value={quant.serial_independent ? 'Independent' : 'Serial Correlation'}
            subValue={`Z-Score: ${quant.runs_zscore.toFixed(2)}`}
            tone={quant.serial_independent ? 'good' : 'warn'}
          />
          <MetricLine
            label="Market Regime (HMM)"
            value={quant.hmm_regime  'Stable'}
            subValue="On-the-fly Classification"
            tone={quant.hmm_regime?.includes('Bull') ? 'good' : 'warn'}
          />

          <div className="mt-3 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Practical Cue</p>
            <p className="text-[12px] text-[var(--text-secondary)] mt-1">
              {Math.abs(runsZ) <= 1.96
                ? 'Market rhythm looks balanced and the current edge appears stable.'
                : runsZ < -1.96
                  ? 'Momentum clustering detected. Slightly tighter risk settings are advisable.'
                  : 'Alternating flow detected. Entry filters can improve timing quality.'}
            </p>
          </div>
        </SectionCard>

        <SectionCard
          icon={TrendingUp}
          title="Client Performance View"
          subtitle="Risk-adjusted quality at a glance"
          accentClass="bg-[rgba(75,163,199,0.08)]"
          className="xl:col-span-4"
        >
          <MetricLine label="Profit Factor" value={pf.toFixed(3)} tone={pf >= 1.5 ? 'good' : pf >= 1.15 ? 'warn' : 'bad'} />
          <MetricLine label="Win Rate" value={`${(winRate * 100).toFixed(1)}%`} tone={winRate >= 0.5 ? 'good' : 'warn'} />
          <MetricLine label="Ratio de Calmar" value={calmar.toFixed(2)} tone={calmar >= 1 ? 'good' : 'warn'} />
          <MetricLine label="Recovery Factor" value={`${Math.min(recovery, 999).toFixed(1)}x`} tone={recovery >= 2 ? 'good' : 'warn'} />
          <MetricLine label="Tail Ratio" value={tailRatio.toFixed(2)} tone={tailRatio >= 1 ? 'good' : 'bad'} />

          <div className="mt-3 rounded-md border border-[var(--bg-border)] bg-[var(--bg-surface)] px-3 py-2">
            <div className="flex items-center justify-between">
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">Quality Signal</p>
              <Activity className="h-3.5 w-3.5 text-[var(--c-info)]" />
            </div>
            <p className="text-[12px] text-[var(--text-secondary)] mt-1">
              {bkScore >= 75
                ? 'Portfolio quality is strong with favorable risk-reward balance.'
                : bkScore >= 55
                  ? 'Quality is solid, but still sensitive to regime shifts.'
                  : 'Quality is vulnerable. Reduce aggressiveness and prioritize capital preservation.'}
            </p>
          </div>
        </SectionCard>
      </div>
    </motion.div>
  )
}
