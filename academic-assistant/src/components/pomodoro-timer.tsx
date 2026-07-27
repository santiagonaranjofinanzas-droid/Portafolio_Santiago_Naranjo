'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, Pause, RotateCcw, X, Target, SkipForward } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface PomodoroTimerProps {
  taskTitle: string;
  onClose: () => void;
}

export function PomodoroTimer({ taskTitle, onClose }: PomodoroTimerProps) {
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const [isActive, setIsActive] = useState(false);
  const [isBreak, setIsBreak] = useState(false);
  const [sessions, setSessions] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout  null>(null);

  useEffect(() => {
    if (isActive && timeLeft > 0) {
      intervalRef.current = setInterval(() => {
        setTimeLeft((prev) => prev - 1);
      }, 1000);
    } else if (timeLeft === 0) {
      setIsActive(false);
      if (!isBreak) {
        setSessions(prev => prev + 1);
        setIsBreak(true);
        setTimeLeft(5 * 60);
      } else {
        setIsBreak(false);
        setTimeLeft(25 * 60);
      }
      try {
        const audio = new Audio('/bell.mp3');
        audio.play().catch(() => {});
      } catch (e) {}
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isActive, timeLeft, isBreak]);

  const toggleTimer = () => setIsActive(!isActive);

  const resetTimer = () => {
    setIsActive(false);
    setIsBreak(false);
    setTimeLeft(25 * 60);
  };

  const skipToNext = () => {
    setIsActive(false);
    if (!isBreak) {
      setIsBreak(true);
      setTimeLeft(5 * 60);
    } else {
      setIsBreak(false);
      setTimeLeft(25 * 60);
    }
  };

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  
  const totalSeconds = isBreak ? 5 * 60 : 25 * 60;
  const progress = ((totalSeconds - timeLeft) / totalSeconds) * 100;

  // SVG circle params
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const dashoffset = circumference - (circumference * progress / 100);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 30 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 30 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="fixed bottom-6 right-6 z-50 w-72"
      >
        <div className="bg-card/90 backdrop-blur-2xl border border-border/40 shadow-2xl shadow-black/10 rounded-3xl overflow-hidden">
          {/* Subtle gradient header */}
          <div className={`px-5 pt-4 pb-3 ${isBreak ? 'bg-emerald-500/[0.04]' : 'bg-primary/[0.04]'}`}>
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <Target className="w-3 h-3 text-primary/60" />
                  <span className={`text-[9px] font-bold uppercase tracking-[0.15em] ${isBreak ? 'text-emerald-500/70' : 'text-primary/60'}`}>
                    {isBreak ? 'Descanso' : 'Enfoque'}
                  </span>
                  {sessions > 0 && (
                    <span className="text-[9px] text-muted-foreground/40 font-medium ml-1">
                      #{sessions + 1}
                    </span>
                  )}
                </div>
                <h3 className="font-semibold text-xs line-clamp-1 text-foreground/80 max-w-[180px]" title={taskTitle}>
                  {taskTitle}
                </h3>
              </div>
              <button 
                onClick={onClose} 
                className="p-1 text-muted-foreground/40 hover:text-foreground/60 hover:bg-muted/40 rounded-lg transition-all"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Timer Display */}
          <div className="flex flex-col items-center justify-center py-6 px-5">
            <div className="relative">
              {/* Progress Circle */}
              <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 120 120">
                <circle 
                  cx="60" cy="60" r={radius} 
                  fill="transparent" 
                  stroke="currentColor" 
                  strokeWidth="4" 
                  className="text-muted/30" 
                />
                <circle 
                  cx="60" cy="60" r={radius} 
                  fill="transparent" 
                  stroke="currentColor" 
                  strokeWidth="4" 
                  className={`transition-all duration-1000 ease-linear ${isBreak ? 'text-emerald-500' : 'text-primary'}`}
                  strokeDasharray={circumference} 
                  strokeDashoffset={dashoffset} 
                  strokeLinecap="round"
                />
              </svg>
              
              {/* Time Text */}
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={`text-3xl font-bold tracking-tight tabular-nums ${isBreak ? 'text-emerald-500' : 'text-foreground'}`}>
                  {minutes.toString().padStart(2, '0')}
                </span>
                <span className={`text-3xl font-bold tracking-tight tabular-nums -mt-1 ${isBreak ? 'text-emerald-500/60' : 'text-foreground/40'}`}>
                  {seconds.toString().padStart(2, '0')}
                </span>
              </div>
            </div>
          </div>

          {/* Controls */}
          <div className="flex justify-center items-center gap-3 px-5 pb-5">
            <Button
              variant="ghost"
              size="icon"
              onClick={resetTimer}
              className="rounded-xl w-9 h-9 text-muted-foreground/50 hover:text-foreground hover:bg-muted/30"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </Button>
            
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTimer}
              className={`rounded-2xl w-14 h-14 transition-all duration-300 ${
                isBreak 
                  ? 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-500'
                  : 'bg-primary/10 hover:bg-primary/20 text-primary'
              }`}
            >
              {isActive ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
            </Button>
            
            <Button
              variant="ghost"
              size="icon"
              onClick={skipToNext}
              className="rounded-xl w-9 h-9 text-muted-foreground/50 hover:text-foreground hover:bg-muted/30"
            >
              <SkipForward className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
