'use client';

import { useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Checkbox } from '@/components/ui/checkbox';
import { supabase } from '@/lib/supabase';

interface ChecklistItem {
  step: string;
  completed: boolean;
}

export function TaskSheet({ task, isOpen, onClose }: { task: any, isOpen: boolean, onClose: () => void }) {
  const [checklist, setChecklist] = useState<ChecklistItem[]>(task?.checklist  []);

  const toggleStep = async (index: number) => {
    const newChecklist = [...checklist];
    newChecklist[index].completed = !newChecklist[index].completed;
    setChecklist(newChecklist);

    // Sync with Supabase
    const { error } = await supabase
      .from('tareas')
      .update({ checklist: newChecklist })
      .eq('id', task.id);
    
    if (error) {
      console.error('Error syncing checklist:', error);
    }
  };

  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent side="right" className="w-[400px] sm:w-[540px]">
        <SheetHeader>
          <SheetTitle>{task?.titulo}</SheetTitle>
          <SheetDescription>
            Detalles de la tarea y hoja de ruta.
          </SheetDescription>
        </SheetHeader>
        
        <div className="mt-8 space-y-6">
          <div>
            <h3 className="text-sm font-semibold mb-3">Lista de verificación</h3>
            <div className="space-y-3">
              {checklist.length > 0 ? (
                checklist.map((item, idx) => (
                  <div key={idx} className="flex items-center space-x-3 bg-muted/30 p-3 rounded-lg border border-transparent hover:border-border transition-all">
                    <Checkbox 
                      id={`item-${idx}`} 
                      checked={item.completed} 
                      onCheckedChange={() => toggleStep(idx)}
                    />
                    <label 
                      htmlFor={`item-${idx}`}
                      className={`text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 ${item.completed ? 'line-through opacity-50' : ''}`}
                    >
                      {item.step}
                    </label>
                  </div>
                ))
              ) : (
                <p className="text-xs text-muted-foreground italic">No hay pasos definidos para esta tarea.</p>
              )}
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
