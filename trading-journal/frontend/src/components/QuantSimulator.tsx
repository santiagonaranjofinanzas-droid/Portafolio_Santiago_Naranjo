'use client'

import { useState, useMemo } from 'react'
import { 
  RefreshCw, BarChart2, CheckCircle2, Sparkles,
  Settings, ArrowRight
} from 'lucide-react'
import EquityChart from './EquityChart'
import { clsx } from 'clsx'

type SimulatedTrade = {
  id: number
  pnl: number
  equity: number
  drawdown: number
  date: string
}

export default function QuantSimulator({ 
  initialBalance = 10000,
  accountLogin = '',
  serverName = ''
}: { 
  initialBalance?: number
  accountLogin?: string
  serverName?: string
}) {
  // Simulator inputs
  const [startCapital, setStartCapital] = useState(initialBalance  10000)
  const [winRate, setWinRate] = useState(55)
  const [profitFactor, setProfitFactor] = useState(1.8)
  const [riskPct, setRiskPct] = useState(1.0)
  const [numTrades, setNumTrades] = useState(100)
  
  // Simulation results state
  const [simData, setSimData] = useState<SimulatedTrade[]>([])
  const [isSimulating, setIsSimulating] = useState(false)

  // Simulation execution function
  const runSimulation = () => {
    setIsSimulating(true)
    
    // Simulate latency to feel premium/alive
    setTimeout(() => {
      let currentEquity = startCapital
      let peak = startCapital
      const trades: SimulatedTrade[] = []
      
      // Calculate win/loss size based on profit factor and risk %
      // Loss size is exactly the risk amount (e.g., 1% of current equity)
      // Win size is risk amount * profit factor
      
      const startDate = new Date()
      startDate.setDate(startDate.getDate() - numTrades)

      // Add baseline starting point
      trades.push({
        id: 0,
        pnl: 0,
        equity: startCapital,
        drawdown: 0,
        date: new Date(startDate).toISOString()
      })

      for (let i = 1; i <= numTrades; i++) {
        const riskVal = currentEquity * (riskPct / 100)
        
        // Random outcome based on Win Rate
        const isWin = Math.random() * 100 < winRate
        const pnl = isWin ? (riskVal * profitFactor) : -riskVal
        
        currentEquity += pnl
        if (currentEquity < 0) currentEquity = 0
        
        peak = Math.max(peak, currentEquity)
        const drawdown = peak > 0 ? (peak - currentEquity) / peak : 0
        
        const tradeDate = new Date(startDate)
        tradeDate.setDate(tradeDate.getDate() + i)

        trades.push({
          id: i,
          pnl,
          equity: currentEquity,
          drawdown,
          date: tradeDate.toISOString()
        })
      }

      setSimData(trades)
      setIsSimulating(false)
    }, 450)
  }

  // Calculate stats from simulated data
  const stats = useMemo(() => {
    if (simData.length <= 1) return null
    const tradesOnly = simData.slice(1)
    
    const wins = tradesOnly.filter(t => t.pnl > 0)
    const losses = tradesOnly.filter(t => t.pnl < 0)
    const netProfit = simData[simData.length - 1].equity - startCapital
    const maxDrawdown = Math.max(...simData.map(t => t.drawdown)) * 100
    
    const winRateReal = (wins.length / tradesOnly.length) * 100
    
    const sumWins = wins.reduce((acc, t) => acc + t.pnl, 0)
    const sumLosses = Math.abs(losses.reduce((acc, t) => acc + t.pnl, 0))
    const pfReal = sumLosses > 0 ? sumWins / sumLosses : 999.0
    
    // Sharpe approximation
    const pnls = tradesOnly.map(t => t.pnl / t.equity)
    const mean = pnls.reduce((acc, v) => acc + v, 0) / pnls.length
    const variance = pnls.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / (pnls.length - 1)
    const stdDev = Math.sqrt(variance)
    const sharpe = stdDev > 0 ? (mean / stdDev) * Math.sqrt(252) : 0.0

    return {
      netProfit,
      finalEquity: simData[simData.length - 1].equity,
      winRateReal,
      pfReal,
      maxDrawdown,
      sharpe,
      winCount: wins.length,
      lossCount: losses.length
    }
  }, [simData, startCapital])

  return (
    <div className="space-y-4">
      {/* Explicación de Calibración / Warmup */}
      <div className="widget bg-gradient-to-r from-blue-900/10 to-indigo-900/5 border-indigo-500/10 p-5">
        <div className="flex items-start gap-4">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Sparkles className="w-4.5 h-4.5 animate-pulse" />
          </div>
          <div>
            <h3 className="text-xs font-black uppercase tracking-wider text-[var(--c-neutral)] flex items-center gap-2">
              Modo Calibración Quant y Simulación Bayesiana
            </h3>
            <p className="text-xs text-[var(--text-muted)] mt-1.5 leading-relaxed">
              Esta cuenta (<strong>{accountLogin  'Sin cuenta'}</strong> · {serverName  'Sin Servidor'}) aún no registra trades en vivo en el sistema. 
              Hemos activado un **Sandbox de Simulación Monte Carlo** para que pruebes la respuesta estadística de tus modelos quant y explores cómo se calculan las métricas en tu panel de control.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Panel Izquierdo: Parámetros del Simulador */}
        <div className="widget flex flex-col justify-between">
          <div>
            <div className="widget-header">
              <div className="widget-title">
                <Settings className="widget-title-icon" />
                Parámetros de Monte Carlo
              </div>
            </div>
            
            <div className="widget-body space-y-4 mt-2">
              {/* Capital Inicial */}
              <div>
                <div className="flex justify-between text-[10px] font-data text-[var(--text-muted)] uppercase font-bold mb-1.5">
                  <span>Capital Inicial</span>
                  <span className="text-[var(--text-secondary)] font-extrabold">${startCapital.toLocaleString()}</span>
                </div>
                <input 
                  type="range" min="1000" max="100000" step="1000" 
                  value={startCapital} 
                  onChange={e => setStartCapital(Number(e.target.value))}
                  className="w-full accent-[var(--c-neutral)]"
                />
              </div>

              {/* Tasa de Victorias */}
              <div>
                <div className="flex justify-between text-[10px] font-data text-[var(--text-muted)] uppercase font-bold mb-1.5">
                  <span>Tasa de Victorias (Win Rate)</span>
                  <span className="text-[var(--text-secondary)] font-extrabold">{winRate}%</span>
                </div>
                <input 
                  type="range" min="20" max="95" step="1" 
                  value={winRate} 
                  onChange={e => setWinRate(Number(e.target.value))}
                  className="w-full accent-[var(--c-neutral)]"
                />
              </div>

              {/* Profit Factor */}
              <div>
                <div className="flex justify-between text-[10px] font-data text-[var(--text-muted)] uppercase font-bold mb-1.5">
                  <span>Profit Factor Teórico</span>
                  <span className="text-[var(--text-secondary)] font-extrabold">{profitFactor.toFixed(1)}x</span>
                </div>
                <input 
                  type="range" min="0.5" max="4.0" step="0.1" 
                  value={profitFactor} 
                  onChange={e => setProfitFactor(Number(e.target.value))}
                  className="w-full accent-[var(--c-neutral)]"
                />
              </div>

              {/* Riesgo por Trade */}
              <div>
                <div className="flex justify-between text-[10px] font-data text-[var(--text-muted)] uppercase font-bold mb-1.5">
                  <span>Riesgo por Trade (R)</span>
                  <span className="text-[var(--text-secondary)] font-extrabold">{riskPct.toFixed(1)}%</span>
                </div>
                <input 
                  type="range" min="0.1" max="5.0" step="0.1" 
                  value={riskPct} 
                  onChange={e => setRiskPct(Number(e.target.value))}
                  className="w-full accent-[var(--c-neutral)]"
                />
              </div>

              {/* Cantidad de Trades */}
              <div>
                <div className="flex justify-between text-[10px] font-data text-[var(--text-muted)] uppercase font-bold mb-1.5">
                  <span>Muestra de Trades</span>
                  <span className="text-[var(--text-secondary)] font-extrabold">{numTrades}</span>
                </div>
                <input 
                  type="range" min="20" max="250" step="10" 
                  value={numTrades} 
                  onChange={e => setNumTrades(Number(e.target.value))}
                  className="w-full accent-[var(--c-neutral)]"
                />
              </div>
            </div>
          </div>

          <div className="pt-4 mt-4 border-t border-[var(--bg-border)]">
            <button 
              onClick={runSimulation}
              disabled={isSimulating}
              className="btn btn-primary w-full py-2.5 justify-center font-bold tracking-wider text-xs uppercase"
            >
              <RefreshCw className={clsx('w-3.5 h-3.5', isSimulating && 'animate-spin')} />
              Regenerar Simulación
            </button>
          </div>
        </div>

        {/* Panel Derecho: Gráfico y Métricas Generadas */}
        <div className="xl:col-span-2 widget">
          <div className="widget-header">
            <div className="widget-title">
              <BarChart2 className="widget-title-icon animate-pulse text-indigo-400" />
              Resultado de Simulación (Curva de Capital)
            </div>
            {stats && (
              <span className="font-data text-xs px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-extrabold">
                Sharpe Simulado: {stats.sharpe.toFixed(2)}
              </span>
            )}
          </div>
          
          {/* KPI Strip Interno de la Simulación */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 p-3 mb-4 rounded-lg bg-[var(--bg-void)] border border-[var(--bg-border)] font-data">
              <div>
                <p className="text-[8px] uppercase tracking-wider text-[var(--text-ghost)] font-bold">Retorno Neto</p>
                <p className={clsx(
                  "text-xs font-black mt-0.5", 
                  stats.netProfit >= 0 ? "text-[var(--c-positive)]" : "text-[var(--c-negative)]"
                )}>
                  {stats.netProfit >= 0 ? '+' : ''}${stats.netProfit.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div>
                <p className="text-[8px] uppercase tracking-wider text-[var(--text-ghost)] font-bold">Win Rate Real</p>
                <p className="text-xs font-black text-[var(--text-secondary)] mt-0.5">
                  {stats.winRateReal.toFixed(1)}% <span className="text-[9px] text-[var(--text-muted)] font-normal">({stats.winCount}/{numTrades})</span>
                </p>
              </div>
              <div>
                <p className="text-[8px] uppercase tracking-wider text-[var(--text-ghost)] font-bold">Profit Factor Real</p>
                <p className="text-xs font-black text-[var(--text-secondary)] mt-0.5">
                  {stats.pfReal.toFixed(2)}x
                </p>
              </div>
              <div>
                <p className="text-[8px] uppercase tracking-wider text-[var(--text-ghost)] font-bold">Max Drawdown</p>
                <p className="text-xs font-black text-[var(--c-negative)] mt-0.5">
                  -{stats.maxDrawdown.toFixed(1)}%
                </p>
              </div>
            </div>
          )}

          <div className="widget-body widget-full">
            <EquityChart data={simData} />
          </div>
        </div>
      </div>

      {/* Checklist de Activación de MT5 en vivo */}
      <div className="widget">
        <div className="widget-header">
          <div className="widget-title">
            <CheckCircle2 className="widget-title-icon text-emerald-400" />
            Checklist de Activación en Vivo para Cuenta {accountLogin  '123456'}
          </div>
        </div>
        <div className="widget-body mt-2">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-[var(--bg-surface)] border border-[var(--bg-border)] flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <span className="w-6 h-6 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-black font-data">01</span>
                  <span className="text-[8px] font-black uppercase text-emerald-400 tracking-wider">Listo</span>
                </div>
                <h4 className="text-xs font-bold text-[var(--text-secondary)]">Detectar Carpeta</h4>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">
                  Encontraste la ruta de datos de tu MT5 (Archivo &gt; Abrir Carpeta de Datos).
                </p>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[var(--bg-surface)] border border-[var(--bg-border)] flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <span className="w-6 h-6 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-black font-data">02</span>
                  <span className="text-[8px] font-black uppercase text-emerald-400 tracking-wider">Listo</span>
                </div>
                <h4 className="text-xs font-bold text-[var(--text-secondary)]">Instalar EA</h4>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">
                  El EA está compilado y cargado en el gráfico con &quot;Allow Algo Trading&quot;.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[var(--bg-surface)] border border-[var(--bg-border)] flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <span className="w-6 h-6 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center text-[10px] font-black font-data">03</span>
                  <span className="text-[8px] font-black uppercase text-amber-400 tracking-wider">Pendiente</span>
                </div>
                <h4 className="text-xs font-bold text-[var(--text-secondary)]">Crear Directory Junction</h4>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">
                  Crea el enlace `mklink /j` en la consola de comandos (CMD) para conectar esta instancia de MT5.
                </p>
              </div>
              <div className="mt-3">
                <a href="file:///c:/Users/YOUR_USERNAME/Desktop/Trading/Proyecto%20Jorunal/Journal_py_original/MT5_MULTICUENTA_GUIA.md" className="text-[9px] text-[var(--c-neutral)] font-bold hover:underline flex items-center gap-1">
                  Ver comandos <ArrowRight className="w-2.5 h-2.5" />
                </a>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[var(--bg-surface)] border border-[var(--bg-border)] flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <span className="w-6 h-6 rounded-full bg-gray-500/10 border border-gray-500/20 text-[var(--text-ghost)] flex items-center justify-center text-[10px] font-black font-data">04</span>
                  <span className="text-[8px] font-black uppercase text-[var(--text-ghost)] tracking-wider">Esperando</span>
                </div>
                <h4 className="text-xs font-bold text-[var(--text-secondary)]">Cerrar un Trade</h4>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">
                  Al cerrar tu primera operación (real o demo) en MT5, la simulación se reemplazará automáticamente con tus datos reales.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
