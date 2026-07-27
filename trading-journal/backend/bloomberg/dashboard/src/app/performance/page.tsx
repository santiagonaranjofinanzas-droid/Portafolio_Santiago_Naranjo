'use client'
import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function PerformancePage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetch('/api/performance').then(r => r.json()).then(d => setData(d));
  }, []);

  if (!data) return <div className="container">Calculando métricas...</div>;
  if (data.error) return <div className="container" style={{ color: 'var(--risk-danger)' }}>Error: {data.error}</div>;

  const chartData = data.nav_history.map((item: any, i: number) => ({ 
    day: i, 
    actual: item.actual,
    theoretical: item.theoretical
  }));

  return (
    <div className="container">
      <div className="glass-panel" style={{ marginBottom: '24px' }}>
        <h3 style={{ marginBottom: '24px' }}>RENDIMIENTO DEL PORTAFOLIO</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px' }}>
          <div>
            <p style={{ opacity: 0.7, marginBottom: '8px', fontSize: '0.9rem' }}>Retorno Total</p>
            <p className="mono" style={{ fontSize: '1.5rem', color: data.total_return >= 0 ? '#00e676' : '#ff1744' }}>
              {(data.total_return * 100).toFixed(2)}%
            </p>
          </div>
          <div>
            <p style={{ opacity: 0.7, marginBottom: '8px', fontSize: '0.9rem' }}>Sharpe Ratio</p>
            <p className="mono" style={{ fontSize: '1.5rem' }}>{data.sharpe_ratio.toFixed(2)}</p>
          </div>
          <div>
            <p style={{ opacity: 0.7, marginBottom: '8px', fontSize: '0.9rem' }}>Volatilidad Anual</p>
            <p className="mono" style={{ fontSize: '1.5rem' }}>{(data.volatility * 100).toFixed(2)}%</p>
          </div>
          <div>
            <p style={{ opacity: 0.7, marginBottom: '8px', fontSize: '0.9rem' }}>Max Drawdown</p>
            <p className="mono" style={{ fontSize: '1.5rem', color: '#ff1744' }}>{(data.max_drawdown * 100).toFixed(2)}%</p>
          </div>
          <div>
            <p style={{ opacity: 0.7, marginBottom: '8px', fontSize: '0.9rem' }}>Win Rate</p>
            <p className="mono" style={{ fontSize: '1.5rem' }}>{(data.win_rate * 100).toFixed(2)}%</p>
          </div>
        </div>
      </div>

      <div className="glass-panel" style={{ height: '400px' }}>
        <h3 style={{ marginBottom: '24px' }}>CURVA DE CAPITAL (NAV)</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <XAxis dataKey="day" stroke="#666" />
            <YAxis stroke="#666" domain={['auto', 'auto']} />
            <Tooltip contentStyle={{ background: '#13151f', border: '1px solid rgba(255,255,255,0.1)' }} />
            <Line type="monotone" name="Real NAV (Manual)" dataKey="actual" stroke="var(--cyan-primary)" strokeWidth={3} dot={false} />
            <Line type="monotone" name="Algoritmo (Teórico)" dataKey="theoretical" stroke="var(--magenta-primary)" strokeWidth={2} strokeDasharray="5 5" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
