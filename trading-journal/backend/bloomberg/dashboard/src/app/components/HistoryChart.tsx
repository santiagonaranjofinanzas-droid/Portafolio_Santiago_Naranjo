'use client'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

export default function HistoryChart({ data }: { data: any[] }) {
  if (!data  data.length === 0) return <div style={{ height: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.5 }}>Esperando puntos de datos...</div>;

  return (
    <div style={{ width: '100%', height: '200px', marginTop: '16px' }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="colorStress" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--cyan-primary)" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="var(--cyan-primary)" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="timestamp" hide />
          <YAxis domain={[0, 1]} hide />
          <Tooltip 
            contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border-glass)', borderRadius: '8px', fontSize: '0.7rem' }}
            itemStyle={{ color: 'var(--cyan-primary)', fontWeight: 'bold' }}
            labelStyle={{ display: 'none' }}
          />
          <Area 
            type="monotone" 
            dataKey="stress" 
            stroke="var(--cyan-primary)" 
            fillOpacity={1} 
            fill="url(#colorStress)" 
            strokeWidth={1.5}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
