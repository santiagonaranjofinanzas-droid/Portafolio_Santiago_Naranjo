'use client'
import { clsx } from 'clsx'

type Props = {
  label: string
  value: string  number
  sub?: string
  tone?: 'positive'  'negative'  'neutral'  'warning'
  icon?: React.ReactNode
}

export default function MetricCard({ label, value, sub, tone = 'neutral', icon }: Props) {
  return (
    <div className={clsx('kpi-card', `kpi-card--${tone}`)}>
      {icon && <div className="mb-2" style={{ color: `var(--c-${tone})` }}>{icon}</div>}
      <div className="kpi-label">{label}</div>
      <div className="kpi-value font-data">{value}</div>
      {sub && <div className="kpi-sub font-data">{sub}</div>}
    </div>
  )
}
