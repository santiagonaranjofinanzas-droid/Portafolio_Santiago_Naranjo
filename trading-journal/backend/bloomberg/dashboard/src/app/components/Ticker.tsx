'use client'

export default function Ticker({ data }: { data: any[] }) {
  if (!data  data.length === 0) return null;

  return (
    <div className="ticker-wrap">
      <div className="ticker">
        {[...data, ...data].map((item, idx) => (
          <div key={idx} className="ticker-item">
            <span className="ticker-symbol" style={{ color: 'var(--cyan-primary)', opacity: 0.8 }}>{item.symbol}</span>
            <span className="ticker-price" style={{ letterSpacing: '1px' }}>{item.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            <span className={`ticker-change ${item.change >= 0 ? 'up' : 'down'}`} style={{ fontSize: '0.7rem', fontWeight: 700 }}>
              {item.change >= 0 ? '+' : ''}{item.change.toFixed(2)}%
            </span>
            <span style={{ marginLeft: '32px', opacity: 0.1 }}>•</span>
          </div>
        ))}
      </div>
    </div>
  );
}
