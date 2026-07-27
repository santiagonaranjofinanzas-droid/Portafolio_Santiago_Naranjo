'use client';

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Calendar, Clock, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { isPast, isToday, isTomorrow, differenceInDays, format } from 'date-fns';
import { es } from 'date-fns/locale';

interface Attachment {
  nombre: string;
  url: string;
}

interface Task {
  id: string;
  materia: string;
  titulo: string;
  descripcion: string;
  fecha_entrega: string;
  estado: string;
  texto_extraido?: string;
  archivos_adjuntos?: Attachment[]  string;
  resumen_ia?: string;
  checklist?: { id: string; text: string; completed: boolean }[];
  tipo?: 'deber'  'prueba';
}

const statusConfig = {
  por_empezar: { 
    bg: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20',
    dot: 'bg-slate-400',
    label: 'Por empezar',
  },
  en_proceso: { 
    bg: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
    dot: 'bg-blue-500',
    label: 'En proceso',
  },
  lista: { 
    bg: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    dot: 'bg-emerald-500',
    label: 'Lista',
  },
  entregada: { 
    bg: 'bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20',
    dot: 'bg-violet-500',
    label: 'Entregada',
  },
};

import { Sparkles as SparklesIcon, Download as DownloadIcon, FileText, Brain, Plus, Trash2, CheckCircle, Play } from 'lucide-react';
import { useState, useMemo } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { supabase } from '@/lib/supabase';
import { PomodoroTimer } from '@/components/pomodoro-timer';

export function TaskCard({ task, showChecklist = false }: { task: Task, showChecklist?: boolean }) {
  const [showSummary, setShowSummary] = useState(false);
  const [showExtracted, setShowExtracted] = useState(false);
  const [newItemText, setNewItemText] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);
  const [showPomodoro, setShowPomodoro] = useState(false);

  // Initialize checklist from task or empty array
  const checklist = useMemo(() => {
    if (!task.checklist) return [];
    if (Array.isArray(task.checklist)) return task.checklist;
    if (typeof task.checklist === 'string') {
      try {
        return JSON.parse(task.checklist);
      } catch {
        return [];
      }
    }
    return [];
  }, [task.checklist]);

  const checklistProgress = useMemo(() => {
    if (checklist.length === 0) return 0;
    return Math.round((checklist.filter((i: any) => i.completed).length / checklist.length) * 100);
  }, [checklist]);

  const handleAddItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newItemText.trim()) return;

    const newItem = {
      id: crypto.randomUUID(),
      text: newItemText.trim(),
      completed: false
    };

    const updatedChecklist = [...checklist, newItem];
    
    // Update Supabase
    const { error } = await supabase
      .from('tareas')
      .update({ checklist: updatedChecklist })
      .eq('id', task.id);

    if (!error) {
      setNewItemText('');
    }
  };

  const handleToggleItem = async (itemId: string) => {
    const updatedChecklist = checklist.map((item: any) => 
      item.id === itemId ? { ...item, completed: !item.completed } : item
    );

    const wasCompleted = updatedChecklist.find((i: any) => i.id === itemId)?.completed;
    
    let updatedEstado = task.estado;
    // Auto move to "en_proceso" if a check is marked and it was "por_empezar"
    if (wasCompleted && task.estado === 'por_empezar') {
      updatedEstado = 'en_proceso';
    }

    const { error } = await supabase
      .from('tareas')
      .update({ 
        checklist: updatedChecklist,
        estado: updatedEstado
      })
      .eq('id', task.id);
  };

  const handleDeleteItem = async (itemId: string) => {
    const updatedChecklist = checklist.filter((item: any) => item.id !== itemId);
    
    await supabase
      .from('tareas')
      .update({ checklist: updatedChecklist })
      .eq('id', task.id);
  };

  // Parse archivos_adjuntos which may be a JSON string or already an array
  const attachments: Attachment[] = useMemo(() => {
    if (!task.archivos_adjuntos) return [];
    if (typeof task.archivos_adjuntos === 'string') {
      try {
        const parsed = JSON.parse(task.archivos_adjuntos);
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    }
    return Array.isArray(task.archivos_adjuntos) ? task.archivos_adjuntos : [];
  }, [task.archivos_adjuntos]);

  const hasSummary = !!task.resumen_ia;
  const hasExtractedText = !!task.texto_extraido && task.texto_extraido.trim().length > 0;

  const isReadyToSubmit = useMemo(() => {
    if (task.estado === 'entregada'  task.estado === 'lista') return false;
    if (!checklist  checklist.length === 0) return false;
    
    const uncompleted = checklist.filter((item: any) => !item.completed);
    if (uncompleted.length === 1) {
      const text = uncompleted[0].text.trim().toLowerCase();
      const keywords = ['enviar', 'subir', 'entregar', 'subir trabajo', 'subir tarea', 'finalizar'];
      return keywords.some(kw => text.includes(kw));
    }
    return false;
  }, [checklist, task.estado]);

  const isOverdue = task.fecha_entrega && isPast(new Date(task.fecha_entrega)) && !isToday(new Date(task.fecha_entrega)) && task.estado !== 'entregada';
  const status = statusConfig[task.estado as keyof typeof statusConfig]  statusConfig.por_empezar;

  // Urgency color for the left accent strip
  const getAccentColor = () => {
    if (isReadyToSubmit) return 'from-emerald-500 to-emerald-400';
    if (isOverdue) return 'from-red-500 to-orange-500';
    if (task.estado === 'en_proceso') return 'from-blue-500 to-cyan-400';
    if (task.estado === 'entregada') return 'from-violet-500 to-purple-400';
    return 'from-slate-400 to-slate-300 dark:from-slate-600 dark:to-slate-500';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ y: -3 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
    >
      <div
        draggable={true}
        onDragStart={(e: React.DragEvent) => {
          e.dataTransfer.setData('taskId', task.id);
        }}
        className="group cursor-grab active:cursor-grabbing h-full"
      >
        <Card className={`glass-card overflow-hidden h-full relative ${
          isReadyToSubmit ? 'ring-1 ring-emerald-500/30 !border-emerald-500/30' : ''
        }`}>
          {/* Left Accent Strip */}
          <div className={`absolute left-0 top-0 bottom-0 w-[3px] bg-gradient-to-b ${getAccentColor()} rounded-l-lg`} />

          <CardHeader className="p-3.5 sm:p-4 pb-2 pl-5">
            <div className="flex justify-between items-start gap-2">
              <div className="flex flex-col gap-1.5 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Badge variant="outline" className="text-[8px] sm:text-[9px] uppercase tracking-[0.1em] font-semibold px-2 py-0.5 w-fit bg-muted/50 border-border/50">
                    {task.materia}
                  </Badge>
                  {isReadyToSubmit && (
                    <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/25 text-[7px] uppercase py-0 px-1.5 animate-pulse font-bold tracking-wider">
                       Listo
                    </Badge>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-1.5 shrink-0">
                {/* Status Pill */}
                <div className={`flex items-center gap-1.5 text-[9px] sm:text-[10px] px-2 py-0.5 rounded-full border font-medium ${status.bg}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
                  {status.label}
                </div>
                {task.estado === 'en_proceso' && (
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-6 w-6 text-blue-500 hover:text-blue-600 hover:bg-blue-500/10 rounded-full"
                    onClick={(e) => { e.stopPropagation(); setShowPomodoro(true); }}
                    title="Modo Enfoque"
                  >
                    <Play className="w-3 h-3 fill-current" />
                  </Button>
                )}
              </div>
            </div>
            
            <CardTitle className="text-sm sm:text-[15px] font-semibold mt-2 group-hover:text-primary transition-colors duration-300 line-clamp-2 leading-snug">
              {task.titulo}
            </CardTitle>
          </CardHeader>
          
          <CardContent className="p-3.5 sm:p-4 pt-0 pl-5">
            <p className="text-[11px] sm:text-xs text-muted-foreground/70 line-clamp-2 mb-3 leading-relaxed">
              {task.descripcion  'Sin descripción adicional.'}
            </p>
            
            {/* Date Row */}
            <div className="flex items-center gap-3 text-[10px] sm:text-[11px] font-medium pb-3 mb-3 border-b border-border/30">
              <div className="flex items-center gap-1.5 text-muted-foreground/70">
                <Calendar className="w-3 h-3" />
                <span>{task.fecha_entrega ? format(new Date(task.fecha_entrega), 'd MMM', { locale: es }) : 'Sin fecha'}</span>
              </div>
              
              {task.fecha_entrega && (
                <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded-md ${
                  isOverdue 
                    ? 'text-red-500 bg-red-500/[0.06]' 
                    : isToday(new Date(task.fecha_entrega)) 
                      ? 'text-amber-500 bg-amber-500/[0.06]' 
                      : 'text-muted-foreground/60'
                }`}>
                  {isOverdue ? (
                    <AlertCircle className="w-3 h-3" />
                  ) : (
                    <Clock className="w-3 h-3" />
                  )}
                  <span className="font-semibold">
                    {isToday(new Date(task.fecha_entrega)) ? 'Hoy' : 
                     isTomorrow(new Date(task.fecha_entrega)) ? 'Mañana' :
                     isOverdue ? 'Vencida' :
                     `${differenceInDays(new Date(task.fecha_entrega), new Date())}d`}
                  </span>
                </div>
              )}

              {/* Checklist mini-progress in date row */}
              {checklist.length > 0 && (
                <div className="flex items-center gap-1.5 ml-auto text-muted-foreground/50">
                  <CheckCircle className="w-3 h-3" />
                  <span className="tabular-nums">{checklist.filter((i: any) => i.completed).length}/{checklist.length}</span>
                </div>
              )}
            </div>
            
            {/* Attachments Section */}
            {attachments.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {attachments.map((archivo, i) => (
                  <a 
                    key={i} 
                    href={archivo.url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg bg-primary/[0.04] border border-primary/10 hover:bg-primary/[0.08] hover:border-primary/20 transition-all text-[10px] text-foreground/70 w-fit max-w-full overflow-hidden group/link"
                  >
                    <DownloadIcon className="w-2.5 h-2.5 flex-shrink-0 text-primary/60 group-hover/link:text-primary transition-colors" />
                    <span className="truncate font-medium">{archivo.nombre}</span>
                  </a>
                ))}
              </div>
            )}
            
            {/* AI Summary Button */}
            {hasSummary && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={(e) => { e.stopPropagation(); setShowSummary(!showSummary); }}
                className="w-full h-7 text-[10px] text-muted-foreground/60 hover:text-primary hover:bg-primary/[0.06] transition-all rounded-lg"
              >
                <Brain className="w-3 h-3 mr-1.5 text-primary/50" />
                {showSummary ? 'Cerrar Resumen IA' : 'Ver Resumen IA'}
              </Button>
            )}
            
            {/* Extracted Text Toggle */}
            {hasExtractedText && !hasSummary && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={(e) => { e.stopPropagation(); setShowExtracted(!showExtracted); }}
                className="w-full h-7 text-[10px] text-muted-foreground/60 hover:text-primary hover:bg-primary/[0.06] transition-all rounded-lg"
              >
                <FileText className="w-3 h-3 mr-1.5 text-primary/50" />
                {showExtracted ? 'Cerrar Texto' : 'Ver Texto Extraído'}
              </Button>
            )}

            {/* No AI indicator when summary is pending */}
            {!hasSummary && !hasExtractedText && task.estado !== 'entregada' && (
              <div className="w-full h-7 flex items-center justify-center text-[9px] text-muted-foreground/30 gap-1">
                <SparklesIcon className="w-2.5 h-2.5" />
                Resumen IA pendiente
              </div>
            )}

            {/* AI Summary Panel */}
            {showSummary && task.resumen_ia && (
              <motion.div 
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                className="mt-3 p-3 rounded-xl bg-primary/[0.04] border border-primary/15 text-[11px] text-muted-foreground/80 whitespace-pre-wrap select-text cursor-text leading-relaxed"
                onPointerDown={(e) => e.stopPropagation()}
              >
                 {task.resumen_ia}
              </motion.div>
            )}

            {/* Extracted Text Panel */}
            {showExtracted && task.texto_extraido && (
              <motion.div 
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                className="mt-3 p-3 rounded-xl bg-muted/20 border border-border/30 text-[11px] text-muted-foreground/70 whitespace-pre-wrap select-text cursor-text max-h-48 overflow-y-auto leading-relaxed"
                onPointerDown={(e) => e.stopPropagation()}
              >
                 {task.texto_extraido}
              </motion.div>
            )}

            {/* Checklist Section */}
            {showChecklist && (
              <div className="mt-4 space-y-3 pt-3 border-t border-border/20">
                {/* Progress Bar */}
                {checklist.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="h-1 w-full bg-muted/40 rounded-full overflow-hidden">
                      <motion.div 
                        className={`h-full rounded-full transition-colors duration-500 ${
                          checklistProgress === 100 ? 'bg-emerald-500' : 'bg-primary/70'
                        }`}
                        initial={{ width: 0 }}
                        animate={{ width: `${checklistProgress}%` }}
                        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                      />
                    </div>
                  </div>
                )}

                {/* Checklist Items */}
                <div className="space-y-1.5">
                  {checklist.map((item: any) => (
                    <div key={item.id} className="flex items-center gap-2 group/item py-0.5 px-1 -mx-1 rounded-md hover:bg-muted/20 transition-colors">
                      <Checkbox 
                        id={item.id} 
                        checked={item.completed}
                        onCheckedChange={() => handleToggleItem(item.id)}
                        className="w-3.5 h-3.5 rounded-[4px]"
                      />
                      <label 
                        htmlFor={item.id}
                        className={`text-[11px] flex-1 cursor-pointer transition-all duration-300 leading-snug ${
                          item.completed 
                            ? 'text-muted-foreground/40 line-through' 
                            : 'text-foreground/75'
                        }`}
                      >
                        {item.text}
                      </label>
                      <button 
                        onClick={() => handleDeleteItem(item.id)}
                        className="opacity-0 group-hover/item:opacity-100 p-0.5 hover:text-red-500 transition-all"
                      >
                        <Trash2 className="w-2.5 h-2.5" />
                      </button>
                    </div>
                  ))}
                </div>

                <form onSubmit={handleAddItem} className="flex gap-1.5">
                  <input
                    type="text"
                    placeholder="Añadir ítem..."
                    value={newItemText}
                    onChange={(e) => setNewItemText(e.target.value)}
                    className="flex-1 bg-muted/20 border border-border/20 rounded-lg px-2.5 py-1.5 text-[11px] focus:ring-1 focus:ring-primary/30 focus:border-primary/30 outline-none transition-all placeholder:text-muted-foreground/30"
                    onClick={(e) => e.stopPropagation()}
                  />
                  <Button type="submit" size="icon" variant="ghost" className="h-7 w-7 shrink-0 rounded-lg hover:bg-primary/[0.06] hover:text-primary">
                    <Plus className="w-3 h-3" />
                  </Button>
                </form>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {showPomodoro && (
        <PomodoroTimer 
          taskTitle={task.titulo} 
          onClose={() => setShowPomodoro(false)} 
        />
      )}
    </motion.div>
  );
}
