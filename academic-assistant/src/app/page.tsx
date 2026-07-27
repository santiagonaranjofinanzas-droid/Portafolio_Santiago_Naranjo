'use client';

import { useEffect, useState, useMemo } from 'react';
import { supabase } from '@/lib/supabase';
import { TaskCard } from '@/components/task-card';
import { Button } from '@/components/ui/button';
import { AnalyticsHeader } from '@/components/analytics-header';
import { CalendarView } from '@/components/calendar-view';
import { ClassSchedule } from '@/components/class-schedule';
import { Archive, LayoutGrid, List, Sparkles, CalendarDays, Clock, Zap } from 'lucide-react';
import { ThemeToggle } from '@/components/theme-toggle';
import { motion, AnimatePresence } from 'framer-motion';
import { Power, PowerOff, ChevronDown, Trophy } from 'lucide-react';
import { startOfWeek, endOfWeek, isWithinInterval } from 'date-fns';

export default function Dashboard() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [view, setView] = useState<'deberes'  'pruebas'  'list'  'calendar'  'schedule'  'archived'>('deberes');
  const [loading, setLoading] = useState(true);
  const [dragOverCol, setDragOverCol] = useState<string  null>(null);
  
  // Automation State
  const [automationConfig, setAutomationConfig] = useState<any>({
    automatizacion_activa: true,
    ultima_ejecucion_scraper: null,
    intervalo_horas: 3
  });

  useEffect(() => {
    fetchTasks();
    fetchAutomationConfig();

    // Subscribe to Realtime changes
    const channel = supabase
      .channel('tasks_channel')
      .on(
        'postgres_changes' as any,
        { event: '*', table: 'tareas' },
        (payload: any) => {
          console.log('Change received!', payload);
          if (payload.eventType === 'INSERT' && !payload.new.archivada) {
            setTasks((prev) => [payload.new, ...prev]);
          } else if (payload.eventType === 'UPDATE') {
            if (payload.new.archivada) {
              setTasks((prev) => prev.filter((t) => t.id !== payload.new.id));
            } else {
              setTasks((prev) => prev.map((t) => (t.id === payload.new.id ? payload.new : t)));
            }
          } else if (payload.eventType === 'DELETE') {
            setTasks((prev) => prev.filter((t) => t.id === payload.old.id));
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  async function fetchTasks() {
    setLoading(true);
    let query = supabase.from('tareas').select('*');
    
    if (view === 'archived') {
      query = query.eq('archivada', true);
    } else {
      query = query.eq('archivada', false);
    }

    const { data, error } = await query
      .order('fecha_entrega', { ascending: true, nullsFirst: false })
      .order('creado_at', { ascending: false });

    if (data) setTasks(data);
    setLoading(false);
  }

  async function fetchAutomationConfig() {
    try {
      const res = await fetch('/api/automation');
      const data = await res.json();
      setAutomationConfig(data);
    } catch (error) {
      console.error('Error fetching automation config:', error);
    }
  }

  // toggleAutomation removed as per user request

  // Reload tasks when view changes to archived/back
  useEffect(() => {
    fetchTasks();
  }, [view]);

  const columns = ['por_empezar', 'en_proceso', 'lista'];

  const handleDrop = async (e: React.DragEvent<HTMLElement>, newEstado: string) => {
    e.preventDefault();
    setDragOverCol(null);
    const taskId = e.dataTransfer.getData('taskId');
    if (!taskId) return;

    // Optimistic UI update
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, estado: newEstado, archivada: newEstado === 'lista' } : t));

    // Supabase update
    const updateData: any = { estado: newEstado };
    if (newEstado === 'lista') {
      updateData.archivada = true;
      updateData.estado = 'entregada'; // Final state
    }

    const { error } = await supabase
      .from('tareas')
      .update(updateData)
      .eq('id', taskId);

    if (error) {
      console.error('Error updating task status:', error);
      fetchTasks(); // Revert on error
    }
  };

  const getTaskType = (t: any) => {
    // If it's explicitly set in DB to 'prueba', trust it.
    // If it's set to 'deber', double check the title just in case.
    const title = t.titulo?.toLowerCase()  '';
    const pruebaKeywords = ['prueba', 'examen', 'test', 'quiz', 'control de lectura', 'leccion', 'lección', 'evaluación', 'evaluacion', 'cuestionario', 'parcial'];
    const isActuallyPrueba = pruebaKeywords.some(kw => title.includes(kw));

    if (t.tipo === 'prueba'  (t.tipo === 'deber' && isActuallyPrueba)) {
      return 'prueba';
    }
    
    return t.tipo  'deber';
  };

  const displayTasks = useMemo(() => {
    let filtered = tasks;
    
    // Apply week filter ONLY to 'list' view as per user request
    if (view === 'list') {
      const now = new Date();
      const weekStart = startOfWeek(now, { weekStartsOn: 1 });
      const weekEnd = endOfWeek(now, { weekStartsOn: 1 });
      
      filtered = tasks.filter(t => {
        if (!t.fecha_entrega) return true;
        const d = new Date(t.fecha_entrega);
        return isWithinInterval(d, { start: weekStart, end: weekEnd });
      });
    }

    if (view === 'deberes') return filtered.filter(t => getTaskType(t) === 'deber');
    if (view === 'pruebas') return filtered.filter(t => getTaskType(t) === 'prueba');
    return filtered;
  }, [tasks, view]);

  // Progress calculation
  const progress = useMemo(() => {
    const completed = displayTasks.filter(t => t.estado === 'lista'  t.estado === 'entregada').length;
    const total = Math.max(displayTasks.length, 1);
    return Math.round((completed / total) * 100);
  }, [displayTasks]);

  const getColMeta = (col: string) => {
    if (col === 'por_empezar') return { 
      bg: 'bg-slate-500/[0.03] hover:bg-slate-500/[0.06] border-slate-500/10',
      dot: 'bg-slate-400',
      label: 'Por Empezar',
      emoji: ''
    };
    if (col === 'en_proceso') return { 
      bg: 'bg-blue-500/[0.03] hover:bg-blue-500/[0.06] border-blue-500/10',
      dot: 'bg-blue-500',
      label: 'En Proceso',
      emoji: ''
    };
    if (col === 'lista') return { 
      bg: 'bg-emerald-500/[0.03] hover:bg-emerald-500/[0.06] border-emerald-500/10',
      dot: 'bg-emerald-500',
      label: 'Lista',
      emoji: ''
    };
    return { bg: 'bg-muted/30', dot: 'bg-muted', label: col, emoji: '' };
  };

  const viewItems = [
    { key: 'deberes', label: 'Deberes', icon: LayoutGrid },
    { key: 'pruebas', label: 'Pruebas & Controles', icon: LayoutGrid },
    { key: 'list', label: 'Lista', icon: List },
    { key: 'calendar', label: 'Calendarios', icon: CalendarDays },
    { key: 'schedule', label: 'Horario', icon: Clock },
    { key: 'archived', label: 'Archivados', icon: Archive },
  ] as const;

  return (
    <main className="min-h-screen dashboard-bg p-4 md:p-8 lg:p-12">
      {/* Ambient Orbs */}
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />

      <div className="max-w-7xl mx-auto relative z-10">
        {/* ───── HEADER ───── */}
        <motion.header 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="mb-10"
        >
          {/* Top Row: Title + System Status */}
          <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 mb-6">
            <div className="flex items-center gap-4">
              {/* Logo Mark */}
              <div className="relative shrink-0">
                <div className="w-12 h-12 rounded-2xl bg-white flex items-center justify-center shadow-lg shadow-emerald-500/20 overflow-hidden border-2 border-emerald-500/20">
                  <img src="/espe-logo.png" alt="ESPE" className="w-10 h-10 object-contain" />
                </div>
                <div className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-emerald-500 border-2 border-background flex items-center justify-center">
                  <Zap className="w-2 h-2 text-white" />
                </div>
              </div>
              
              <div>
                <h1 className="text-2xl md:text-3xl font-bold tracking-tight bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent">
                  Asistente Académico
                </h1>
                <p className="text-muted-foreground text-xs md:text-sm font-medium mt-0.5">
                  Gestión inteligente de tareas y recursos universitarios
                </p>
              </div>

              {/* Progress Pill */}
              <button 
                onClick={() => {
                  const el = document.getElementById('task-content');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
                className="hidden xl:flex items-center gap-2.5 ml-6 px-4 py-2 bg-emerald-500/[0.06] border border-emerald-500/15 rounded-2xl backdrop-blur-sm hover:bg-emerald-500/10 transition-colors cursor-pointer group"
              >
                <div className="relative w-8 h-8">
                  <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                    <circle cx="18" cy="18" r="14" fill="transparent" stroke="currentColor" strokeWidth="3" className="text-emerald-500/10" />
                    <circle 
                      cx="18" cy="18" r="14" 
                      fill="transparent" 
                      stroke="currentColor" 
                      strokeWidth="3" 
                      className="text-emerald-500 transition-all duration-1000 ease-out" 
                      strokeDasharray="87.96" 
                      strokeDashoffset={87.96 - (87.96 * progress / 100)} 
                      strokeLinecap="round"
                    />
                  </svg>
                  <Trophy className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="flex flex-col text-left">
                  <span className="text-[9px] font-bold uppercase tracking-[0.15em] text-emerald-600/60">Tu Avance</span>
                  <span className="text-sm font-bold tracking-tight text-foreground">{progress}%</span>
                </div>
              </button>
            </div>

            {/* Automation Chip */}
            <div className="flex items-center gap-3 px-4 py-2.5 bg-card/60 backdrop-blur-xl rounded-2xl border border-border/40 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <div className={`w-2 h-2 rounded-full ${automationConfig.automatizacion_activa ? 'bg-emerald-500' : 'bg-red-400'}`} />
                  {automationConfig.automatizacion_activa && (
                    <div className="absolute inset-0 w-2 h-2 rounded-full bg-emerald-500 animate-ping opacity-50" />
                  )}
                </div>
                <div className="flex flex-col">
                  <span className={`text-[10px] font-bold ${automationConfig.automatizacion_activa ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400'}`}>
                    {automationConfig.automatizacion_activa ? 'SISTEMA ACTIVO' : 'PAUSADO'}
                  </span>
                  {automationConfig.ultima_ejecucion_scraper && (
                    <span className="text-[9px] text-muted-foreground/50 font-medium">
                      Última: {new Date(automationConfig.ultima_ejecucion_scraper).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="w-full overflow-x-auto no-scrollbar">
            <div className="flex items-center gap-1 p-1 rounded-xl bg-card/40 backdrop-blur-sm border border-border/30 w-fit min-w-full sm:min-w-0">
              {viewItems.map(({ key, label, icon: Icon }) => (
                <Button
                  key={key}
                  variant="ghost"
                  size="sm"
                  onClick={() => setView(key as typeof view)}
                  className={`h-9 px-4 shrink-0 rounded-lg font-medium text-xs transition-all duration-200 ${
                    view === key 
                      ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20 hover:bg-primary/90 hover:text-primary-foreground' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 mr-1.5" />
                  {label}
                </Button>
              ))}
              <div className="w-px h-5 bg-border/30 mx-1 shrink-0" />
              <ThemeToggle />
            </div>
          </div>
        </motion.header>

        {/* ───── ANALYTICS ───── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
        >
          <AnalyticsHeader tasks={displayTasks} />
        </motion.div>

        {/* ───── CONTENT ───── */}
        <motion.div
          id="task-content"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
        >
          {loading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
              <div className="flex gap-1.5">
                {[0, 1, 2].map(i => (
                  <div 
                    key={i} 
                    className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" 
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
              <p className="text-sm text-muted-foreground font-medium">Cargando tareas...</p>
            </div>
          ) : view === 'schedule' ? (
            <ClassSchedule />
          ) : view === 'calendar' ? (
            <div className="space-y-12">
              <div className="space-y-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-1.5 h-6 bg-primary rounded-full" />
                  <h2 className="text-xl font-bold tracking-tight">Calendario de Deberes</h2>
                </div>
                <CalendarView tasks={tasks.filter(t => getTaskType(t) === 'deber')} />
              </div>
              
              <div className="space-y-4 pt-8 border-t border-border/40">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-1.5 h-6 bg-purple-500 rounded-full" />
                  <h2 className="text-xl font-bold tracking-tight">Calendario de Pruebas & Controles</h2>
                </div>
                <CalendarView tasks={tasks.filter(t => getTaskType(t) === 'prueba')} />
              </div>
            </div>
          ) : view === 'list' ? (
            <div className="space-y-10">
              {[
                { label: 'Lunes', index: 1 },
                { label: 'Martes', index: 2 },
                { label: 'Miércoles', index: 3 },
                { label: 'Jueves', index: 4 },
                { label: 'Viernes', index: 5 },
                { label: 'Sábado', index: 6 },
                { label: 'Domingo', index: 0 },
                { label: 'Sin fecha', index: -1 }
              ].map((day) => {
                const dayTasks = displayTasks.filter((t: any) => {
                  if (!t.fecha_entrega) return day.index === -1;
                  const d = new Date(t.fecha_entrega);
                  return d.getDay() === day.index && day.index !== -1;
                });

                if (dayTasks.length === 0 && day.label !== 'Sin fecha') return null;
                if (dayTasks.length === 0 && day.label === 'Sin fecha' && displayTasks.every(t => t.fecha_entrega)) return null;

                return (
                  <div key={day.label} className="space-y-4">
                    <div className="flex items-center gap-4 px-1">
                      <h2 className="text-xs font-bold uppercase tracking-[0.25em] text-muted-foreground/60">
                        {day.label}
                      </h2>
                      <div className="h-px flex-1 bg-gradient-to-r from-border/50 to-transparent" />
                      <span className="text-[10px] font-bold px-2.5 py-0.5 bg-primary/[0.06] text-primary rounded-full border border-primary/15">
                        {dayTasks.length}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                      {dayTasks.map((task: any) => (
                        <TaskCard key={task.id} task={task} showChecklist={true} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* ───── KANBAN BOARD ───── */
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
              <AnimatePresence mode="popLayout">
                {columns.map((col: string) => {
                  const meta = getColMeta(col);
                  const colTasks = displayTasks.filter((t: any) => t.estado === col);
                  const isDragOver = dragOverCol === col;
                  
                  return (
                    <motion.section 
                      key={col}
                      layout
                      className={`space-y-4 p-4 rounded-2xl border transition-all duration-300 min-h-[500px] ${meta.bg} ${
                        isDragOver ? 'ring-2 ring-primary/30 ring-offset-2 ring-offset-background scale-[1.01]' : ''
                      }`}
                      onDragOver={(e) => { e.preventDefault(); setDragOverCol(col); }}
                      onDragLeave={() => setDragOverCol(null)}
                      onDrop={(e) => handleDrop(e, col)}
                    >
                      {/* Column Header */}
                      <div className="flex justify-between items-center px-1 pb-2">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${meta.dot}`} />
                          <h2 className="text-[11px] font-bold uppercase tracking-[0.2em] text-muted-foreground/70">
                            {meta.label}
                          </h2>
                        </div>
                        <span className="text-[10px] font-bold px-2.5 py-0.5 bg-background/80 backdrop-blur-sm rounded-full border border-border/50 shadow-sm tabular-nums">
                          {colTasks.length}
                        </span>
                      </div>
                      
                      {/* Task Cards */}
                      <div className="space-y-3">
                        {colTasks.map((task: any) => (
                          <TaskCard key={task.id} task={task} showChecklist={true} />
                        ))}
                        {colTasks.length === 0 && (
                          <div className={`border-2 border-dashed rounded-xl h-28 flex flex-col items-center justify-center gap-2 transition-all duration-300 ${
                            isDragOver ? 'border-primary/40 bg-primary/[0.04]' : 'border-border/30'
                          }`}>
                            <span className="text-lg opacity-30">{meta.emoji}</span>
                            <span className="text-muted-foreground/30 text-[10px] font-medium">
                              Arrastra tareas aquí
                            </span>
                          </div>
                        )}
                      </div>
                    </motion.section>
                  );
                })}
              </AnimatePresence>
            </div>
          )}
        </motion.div>
      </div>
    </main>
  );
}
