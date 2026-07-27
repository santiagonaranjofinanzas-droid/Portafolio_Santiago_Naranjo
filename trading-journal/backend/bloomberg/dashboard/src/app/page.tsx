'use client'
import { usePollingState } from '@/hooks/usePolling';
import Ticker from './components/Ticker';
import HistoryChart from './components/HistoryChart';
import AgentConsensus from './components/AgentConsensus';
import { Activity, ShieldCheck, Zap, Newspaper } from 'lucide-react';

export default function DashboardPage() {
  const { data, error, isLoading } = usePollingState();

  if (isLoading) return <div className="container">Cargando Terminal...</div>;
  if (error) return <div className="container" style={{ color: 'var(--risk-danger)' }}>Error: {error.message}</div>;
  if (!data) return <div className="container">Cargando Terminal...</div>;

  const { quant, mirofish, portfolio, ticker, history, news, weights } = data;
  const drawdown = ((portfolio.nav - portfolio.hwm) / portfolio.hwm) * 100;
  
  let riskColor = 'var(--risk-safe)';
  if (drawdown < -5) riskColor = 'var(--risk-warn)';
  if (drawdown < -8) riskColor = 'var(--risk-danger)';

  const toPct = (value: any) => Math.max(0, Math.round((Number(value)  0) * 100));
  const qqqWeight = weights?.QQQ ?? 0;
  const gldWeight = weights?.GLD ?? 0;
  const cashWeight = weights?.CASH ?? Math.max(0, 1 - qqqWeight - gldWeight);

  const targetQQQ = toPct(qqqWeight);
  const targetGLD = toPct(gldWeight);
  const targetCASH = toPct(cashWeight);

  return (
    <>
      <div className="scanline" />
      <Ticker data={ticker} />
      
      <div className="container">
        {/* Superior: Panorama de Riesgo Global */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginBottom: '24px' }}>
          <div className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderLeft: `4px solid ${riskColor}` }}>
            <div>
              <p style={{ fontSize: '0.65rem', opacity: 0.4, textTransform: 'uppercase', letterSpacing: '2px' }}>Valor Liquidativo de la Cartera (USD)</p>
              <div className="mono" style={{ fontSize: '2.2rem', fontWeight: 700, letterSpacing: '-1px' }}>
                ${portfolio.nav.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <p style={{ fontSize: '0.65rem', opacity: 0.4, textTransform: 'uppercase', letterSpacing: '2px' }}>Descenso del nivel máximo al mínimo</p>
              <div className="mono" style={{ fontSize: '1.8rem', color: riskColor, fontWeight: 600 }}>{drawdown.toFixed(2)}%</div>
            </div>
          </div>

          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', background: 'rgba(0, 212, 255, 0.03)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: riskColor, boxShadow: `0 0 10px ${riskColor}` }} />
              <div>
                <p style={{ fontSize: '0.6rem', opacity: 0.5, textTransform: 'uppercase' }}>Estado del Motor</p>
                <div className="mono" style={{ fontSize: '0.9rem', fontWeight: 600 }}>{drawdown < -8 ? 'OPERACIÓN DE EMERGENCIA' : 'SISTEMA NOMINAL'}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid-3">
          {/* COL 1: QUANTITATIVE ANALYTICS */}
          <div className="glass-panel" style={{ borderTop: '2px solid var(--cyan-primary)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--cyan-primary)', letterSpacing: '1px' }}>[ QUANT.CORE.HMM ]</span>
              <Activity size={14} color="var(--cyan-primary)" />
            </div>
            
            <div style={{ marginBottom: '24px' }}>
              <p style={{ opacity: 0.4, marginBottom: '4px', fontSize: '0.75rem' }}>STRESS PROBABILITY (T+5)</p>
              <div className="mono" style={{ fontSize: '3rem', color: 'var(--cyan-primary)', fontWeight: 700, textShadow: '0 0 20px var(--cyan-glow)' }}>
                {(quant.stress_probability_t5 * 100).toFixed(1)}%
              </div>
            </div>

            <HistoryChart data={history} />

            <div style={{ marginTop: '24px' }}>
              <p style={{ opacity: 0.4, marginBottom: '12px', fontSize: '0.7rem', letterSpacing: '1px' }}>HMM REGIME DISTRIBUTION</p>
              <div style={{ display: 'flex', gap: '6px', marginBottom: '12px' }}>
                <div style={{ flex: quant.regime_probabilities.low, height: '6px', background: 'var(--risk-safe)', borderRadius: '3px', boxShadow: '0 0 5px var(--risk-safe)' }} />
                <div style={{ flex: quant.regime_probabilities.transition, height: '6px', background: 'var(--risk-warn)', borderRadius: '3px' }} />
                <div style={{ flex: quant.regime_probabilities.high, height: '6px', background: 'var(--risk-danger)', borderRadius: '3px' }} />
              </div>
              <div className="mono" style={{ fontSize: '0.6rem', display: 'flex', justifyContent: 'space-between', opacity: 0.4 }}>
                <span>LOW VOL</span>
                <span>SYSTEMIC</span>
              </div>
            </div>
          </div>

          {/* COL 2: PORTFOLIO ALLOCATION */}
          <div className="glass-panel" style={{ borderTop: '2px solid #fff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '1px' }}>[ BLACK.LITTERMAN.OPT ]</span>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.75rem' }}>
                  <span style={{ opacity: 0.6 }}>QQQ (Equity)</span>
                  <span className="mono" style={{ fontWeight: 600 }}>{targetQQQ}%</span>
                </div>
                <div className="cyber-progress">
                  <div className="cyber-progress-fill" style={{ width: `${targetQQQ}%`, background: '#fff', color: 'rgba(255,255,255,0.4)' }} />
                </div>
              </div>
              
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.75rem' }}>
                  <span style={{ opacity: 0.6 }}>GLD (Hedging)</span>
                  <span className="mono" style={{ fontWeight: 600 }}>{targetGLD}%</span>
                </div>
                <div className="cyber-progress">
                  <div className="cyber-progress-fill" style={{ width: `${targetGLD}%`, background: 'var(--gold-primary)', color: 'var(--gold-glow)' }} />
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.75rem' }}>
                  <span style={{ opacity: 0.6 }}>CASH (Safety)</span>
                  <span className="mono" style={{ fontWeight: 600 }}>{targetCASH}%</span>
                </div>
                <div className="cyber-progress">
                  <div className="cyber-progress-fill" style={{ width: `${targetCASH}%`, background: 'var(--risk-safe)', color: 'var(--risk-safe)' }} />
                </div>
              </div>
            </div>

            <div style={{ marginTop: '32px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <Newspaper size={12} style={{ opacity: 0.5 }} />
                <span style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '1px', opacity: 0.5 }}>INSTITUTIONAL FEED</span>
              </div>
              <div className="news-feed" style={{ maxHeight: '160px' }}>
                {news.length > 0 ? news.map((n: any, i: number) => (
                  <div key={i} className="news-item" style={{ fontSize: '0.75rem' }}>
                    <span style={{ color: 'var(--cyan-primary)', marginRight: '6px', fontSize: '0.65rem' }}>{n.source.toUpperCase()}</span>
                    {n.title}
                  </div>
                )) : <p style={{ opacity: 0.2, fontSize: '0.7rem' }}>Scanning markets...</p>}
              </div>
            </div>
          </div>

          {/* COL 3: NARRATIVE INTELLIGENCE */}
          <div className="glass-panel" style={{ borderTop: '2px solid var(--magenta-primary)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--magenta-primary)', letterSpacing: '1px' }}>[ MIROFISH.SWARM.v2 ]</span>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
              <div style={{ background: 'rgba(188, 19, 254, 0.05)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(188, 19, 254, 0.1)' }}>
                <p style={{ opacity: 0.4, fontSize: '0.55rem', marginBottom: '4px', letterSpacing: '1px' }}>NARRATIVE R</p>
                <div className="mono" style={{ fontSize: '1.2rem', color: 'var(--magenta-primary)', fontWeight: 600 }}>{mirofish.R_narr.toFixed(2)}</div>
              </div>
              <div style={{ background: 'rgba(188, 19, 254, 0.05)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(188, 19, 254, 0.1)' }}>
                <p style={{ opacity: 0.4, fontSize: '0.55rem', marginBottom: '4px', letterSpacing: '1px' }}>OMEGA (UNC)</p>
                <div className="mono" style={{ fontSize: '1.2rem', color: 'var(--magenta-primary)', fontWeight: 600 }}>{mirofish.omega_narr.toFixed(2)}</div>
              </div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-glass)', minHeight: '180px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span className="mono" style={{ fontSize: '0.65rem', color: 'var(--magenta-primary)', fontWeight: 700 }}>
                  THEME: {mirofish.dominant_theme.toUpperCase()}
                </span>
                <span className="mono" style={{ fontSize: '0.6rem', opacity: 0.5 }}>
                  CONF: {(mirofish.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p style={{ fontSize: '0.8rem', lineHeight: '1.6', opacity: 0.8, fontStyle: 'italic' }}>
                "{mirofish.reasoning}"
              </p>
            </div>

            <AgentConsensus mirofish={mirofish} />
          </div>
        </div>
      </div>
    </>
  );
}
