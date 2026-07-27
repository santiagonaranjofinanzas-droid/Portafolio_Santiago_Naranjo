'use client'
import { Brain, ShieldAlert, TrendingUp } from 'lucide-react';

export default function AgentConsensus({ mirofish }: { mirofish: any }) {
  const snippets = mirofish?.agent_snippets  {};
  
  const agents = [
    { 
      name: 'Macro', 
      icon: TrendingUp, 
      status: snippets.macro ? 'SINC' : 'STANDBY', 
      color: snippets.macro ? 'var(--cyan-primary)' : '#888',
      desc: snippets.macro  'Esperando pulso...'
    },
    { 
      name: 'Sentimiento', 
      icon: Brain, 
      status: snippets.sentiment ? 'SINC' : 'STANDBY', 
      color: snippets.sentiment ? 'var(--magenta-primary)' : '#888',
      desc: snippets.sentiment  'Analizando feed...'
    },
    { 
      name: 'Riesgo', 
      icon: ShieldAlert, 
      status: snippets.risk ? 'SINC' : 'STANDBY', 
      color: snippets.risk ? 'var(--risk-danger)' : '#888',
      desc: snippets.risk  'Calculando &Omega;...'
    }
  ];

  return (
    <div style={{ display: 'flex', gap: '8px', marginTop: '20px' }}>
      {agents.map((agent, i) => (
        <div key={i} className="agent-bubble" style={{ flex: 1, textAlign: 'center', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }} title={agent.desc}>
          <agent.icon size={12} style={{ color: agent.color, marginBottom: '4px' }} />
          <div style={{ opacity: 0.4, fontSize: '0.55rem', textTransform: 'uppercase' }}>{agent.name}</div>
          <div style={{ fontWeight: 'bold', color: agent.color, fontSize: '0.65rem' }}>{agent.status}</div>
        </div>
      ))}
    </div>
  );
}
