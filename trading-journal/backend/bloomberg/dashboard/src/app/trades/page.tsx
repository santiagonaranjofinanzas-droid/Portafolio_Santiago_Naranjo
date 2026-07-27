'use client'
import { useState, useEffect } from 'react';

export default function TradesPage() {
  const [trades, setTrades] = useState([]);
  const [asset, setAsset] = useState('QQQ');
  const [type, setType] = useState('BUY');
  const [price, setPrice] = useState('');
  const [shares, setShares] = useState('');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    fetch('/api/trades').then(r => r.json()).then(data => setTrades(Array.isArray(data) ? data : []));
  }, []);

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    const p = parseFloat(price);
    const s = parseFloat(shares);
    await fetch('/api/trades', {
      method: 'POST',
      body: JSON.stringify({
        asset, type, entry_price: p, shares: s, capital_usd: p * s, notes
      })
    });
    fetch('/api/trades').then(r => r.json()).then(data => setTrades(data));
  };

  return (
    <div className="container">
      <div className="glass-panel" style={{ marginBottom: '24px' }}>
        <h3 style={{ marginBottom: '24px' }}>REGISTRAR NUEVA ENTRADA</h3>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <select value={asset} onChange={e => setAsset(e.target.value)} style={{ padding: '12px', background: 'var(--bg-surface)', color: 'white', border: '1px solid var(--border-glass)', borderRadius: '8px' }}>
            <option value="QQQ">QQQ</option>
            <option value="GLD">GLD</option>
            <option value="CASH">CASH</option>
          </select>
          <select value={type} onChange={e => setType(e.target.value)} style={{ padding: '12px', background: 'var(--bg-surface)', color: 'white', border: '1px solid var(--border-glass)', borderRadius: '8px' }}>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
          <input type="number" placeholder="Precio ($)" value={price} onChange={e => setPrice(e.target.value)} style={{ padding: '12px', background: 'var(--bg-surface)', color: 'white', border: '1px solid var(--border-glass)', borderRadius: '8px' }} />
          <input type="number" placeholder="Shares" value={shares} onChange={e => setShares(e.target.value)} style={{ padding: '12px', background: 'var(--bg-surface)', color: 'white', border: '1px solid var(--border-glass)', borderRadius: '8px' }} />
          <input type="text" placeholder="Notas" value={notes} onChange={e => setNotes(e.target.value)} style={{ gridColumn: 'span 2', padding: '12px', background: 'var(--bg-surface)', color: 'white', border: '1px solid var(--border-glass)', borderRadius: '8px' }} />
          <button type="submit" style={{ gridColumn: 'span 2', padding: '14px', background: 'white', color: 'black', border: 'none', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer' }}>
            REGISTRAR OPERACIÓN
          </button>
        </form>
      </div>

      <div className="glass-panel">
        <h3 style={{ marginBottom: '24px' }}>POSICIONES HISTÓRICAS</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-glass)' }}>
              <th style={{ padding: '12px' }}>Asset</th>
              <th style={{ padding: '12px' }}>Type</th>
              <th style={{ padding: '12px' }}>Entry Price</th>
              <th style={{ padding: '12px' }}>Shares</th>
              <th style={{ padding: '12px' }}>Capital</th>
              <th style={{ padding: '12px' }}>Date</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t: any) => (
              <tr key={t.id} style={{ borderBottom: '1px solid var(--border-glass)' }}>
                <td style={{ padding: '12px' }} className="mono">{t.asset}</td>
                <td style={{ padding: '12px', color: t.type === 'BUY' ? '#00e676' : '#ff1744' }}>{t.type}</td>
                <td style={{ padding: '12px' }} className="mono">${t.entry_price.toFixed(2)}</td>
                <td style={{ padding: '12px' }} className="mono">{t.shares.toFixed(2)}</td>
                <td style={{ padding: '12px' }} className="mono">${t.capital_usd.toFixed(2)}</td>
                <td style={{ padding: '12px', fontSize: '0.9rem', opacity: 0.7 }}>{new Date(t.entry_date).toLocaleString()}</td>
              </tr>
            ))}
            {trades.length === 0 && <tr><td colSpan={6} style={{ padding: '24px', textAlign: 'center', opacity: 0.5 }}>Sin operaciones registradas</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
