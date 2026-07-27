'use client';

import { Card } from './ui/card';
import { Target, CheckCircle, CalendarDays, Clock, TrendingUp, AlertTriangle } from 'lucide-react';
import { differenceInDays, isBefore, addDays } from 'date-fns';
import { motion } from 'framer-motion';

export function AnalyticsHeader({ tasks }: { tasks: any[] }) {
  const activeTasks = tasks.length;
  const materiaCounts: Record<string, number> = {};
  
  tasks.forEach(t => {
    if (t.materia) materiaCounts[t.materia] = (materiaCounts[t.materia]  0) + 1;
  });
  
  let maxMateria = 'Ninguna';
  let maxCount = 0;
  for (const [materia, count] of Object.entries(materiaCounts)) {
    if (count > maxCount) {
      maxCount = count;
      maxMateria = materia;
    }
  }

  const now = new Date();
  const next7Days = addDays(now, 7);

  const proximas = tasks.filter((t) => {
    if (!t.fecha_entrega  t.estado === 'lista'  t.archivada) return false;
    const due = new Date(t.fecha_entrega);
    return isBefore(due, next7Days) && isBefore(now, due);
  }).length;

  const vencidas = tasks.filter((t) => {
    if (!t.fecha_entrega  t.estado === 'lista'  t.archivada) return false;
    return isBefore(new Date(t.fecha_entrega), now);
  }).length;

  const cards = [
    {
      label: 'Tareas Activas',
      value: activeTasks,
      icon: Target,
      color: 'text-primary',
      bgColor: 'bg-primary/[0.08]',
      borderColor: 'border-primary/15',
      delay: 0,
    },
    {
      label: 'Foco Principal',
      value: maxMateria,
      subtitle: `${maxCount} tareas pendientes`,
      icon: TrendingUp,
      color: 'text-violet-500',
      bgColor: 'bg-violet-500/[0.08]',
      borderColor: 'border-violet-500/15',
      delay: 0.05,
    },
    {
      label: 'Esta Semana',
      value: proximas,
      icon: CalendarDays,
      color: 'text-blue-500',
      bgColor: 'bg-blue-500/[0.08]',
      borderColor: 'border-blue-500/15',
      delay: 0.1,
    },
    {
      label: 'Vencidas',
      value: vencidas,
      icon: vencidas > 0 ? AlertTriangle : Clock,
      color: vencidas > 0 ? 'text-red-500' : 'text-muted-foreground',
      bgColor: vencidas > 0 ? 'bg-red-500/[0.08]' : 'bg-muted/50',
      borderColor: vencidas > 0 ? 'border-red-500/15' : 'border-border/50',
      urgent: vencidas > 0,
      delay: 0.15,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-8">
      {cards.map((card, idx) => (
        <motion.div
          key={card.label}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: card.delay, ease: [0.22, 1, 0.36, 1] }}
        >
          <Card className={`glass-card p-3.5 sm:p-4 flex items-center gap-3 group overflow-hidden relative ${card.borderColor}`}>
            {/* Subtle gradient background on hover */}
            <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 ${card.bgColor}`} />
            
            <div className={`relative z-10 p-2.5 rounded-xl ${card.bgColor} ${card.color} shrink-0 transition-transform duration-300 group-hover:scale-110`}>
              <card.icon className="w-4 h-4 sm:w-5 sm:h-5" />
            </div>
            
            <div className="relative z-10 overflow-hidden min-w-0">
              <p className="text-[9px] sm:text-[10px] text-muted-foreground font-semibold uppercase tracking-[0.12em] truncate">
                {card.label}
              </p>
              {typeof card.value === 'number' ? (
                <h3 className={`text-xl sm:text-2xl font-bold leading-tight tracking-tight ${card.urgent ? 'text-red-500' : ''}`}>
                  {card.value}
                </h3>
              ) : (
                <>
                  <h3 className="text-xs sm:text-sm font-bold truncate mt-0.5 leading-tight" title={card.value as string}>
                    {card.value}
                  </h3>
                  {card.subtitle && (
                    <span className="hidden sm:inline text-[9px] text-muted-foreground/60 font-medium">
                      {card.subtitle}
                    </span>
                  )}
                </>
              )}
            </div>

            {/* Urgent pulse */}
            {card.urgent && (
              <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            )}
          </Card>
        </motion.div>
      ))}
    </div>
  );
}
