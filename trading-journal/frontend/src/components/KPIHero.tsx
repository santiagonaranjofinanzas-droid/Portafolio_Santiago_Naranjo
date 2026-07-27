'use client'
import { clsx } from 'clsx'

type Props = {
  label: string
  value: string  number
  sub?: string
  icon?: React.ReactNode
  className?: string
}

export default function KPIHero({ label, value, sub, icon, className }: Props) {
  const numVal = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''))
  const tone = isNaN(numVal) ? 'neutral' : numVal > 0 ? 'positive' : numVal < 0 ? 'negative' : 'neutral'

  return (
    <div className={clsx('kpi-card', `kpi-card--${tone}`, className)}>
      {icon && <div className="mb-1" style={{ color: `var(--c-${tone})` }}>{icon}</div>}
      <div className="kpi-label">{label}</div>
      <div className={clsx('kpi-value font-data', tone === 'positive' && 'text-[var(--c-positive)]', tone === 'negative' && 'text-[var(--c-negative)]')}>
        {value}
      </div>
      {sub && <div className="kpi-sub font-data">{sub}</div>}
    </div>
  )
}
