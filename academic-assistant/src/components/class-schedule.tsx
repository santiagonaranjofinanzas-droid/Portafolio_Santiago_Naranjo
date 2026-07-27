"use client";

import { motion } from "framer-motion";
import { Clock, Video, Globe, Briefcase, GraduationCap, Code, ShieldCheck, MapPin } from "lucide-react";

interface ScheduleItem {
  id: string;
  name: string;
  time: string;
  day: number;
  duration: number; // hours
  link: string;
  type: 'zoom'  'teams'  'none';
  color: string;
  icon: any;
  passcode?: string;
}

const SCHEDULE: ScheduleItem[] = [
  { id: "1", name: "Liderazgo", time: "17:00", day: 1, duration: 2, link: "https://cedia.zoom.us/j/9771620453", type: "zoom", color: "bg-teal-500/10 border-teal-500/20 text-teal-600 dark:text-teal-400", icon: Globe },
  { id: "2", name: "Economía Internacional", time: "17:00", day: 2, duration: 2, link: "https://cedia.zoom.us/j/86307638374", type: "zoom", color: "bg-purple-500/10 border-purple-500/20 text-purple-600 dark:text-purple-400", icon: Globe },
  { id: "3", name: "Finanzas Corporativas", time: "19:00", day: 2, duration: 2, link: "https://teams.microsoft.com/meet/2946832374372?p=c3WgUYqFcaqguCveKy", type: "teams", color: "bg-blue-500/10 border-blue-500/20 text-blue-600 dark:text-blue-400", icon: Briefcase, passcode: "Passcode: dC9Lc2Gb" },
  { id: "4", name: "Economías Innovadoras", time: "19:00", day: 3, duration: 2, link: "https://teams.microsoft.com/meet/23496449269621?p=KyyMtCOKF6Nr6YcJio", type: "teams", color: "bg-pink-500/10 border-pink-500/20 text-pink-600 dark:text-pink-400", icon: GraduationCap, passcode: "Passcode: Eq32d7nB" },
  { id: "5", name: "Gestión y Emprendimiento", time: "17:00", day: 4, duration: 2, link: "https://cedia.zoom.us/j/87298006049", type: "zoom", color: "bg-orange-500/10 border-orange-500/20 text-orange-600 dark:text-orange-400", icon: Code },
  { id: "6", name: "Gestión de la Calidad", time: "19:00", day: 4, duration: 2, link: "https://us06web.zoom.us/j/89636651652?pwd=QsG66CxRrhcc4kH4W63yTyXb7FStua.1", type: "zoom", color: "bg-amber-700/10 border-amber-700/20 text-amber-700 dark:text-amber-500", icon: ShieldCheck },
  { id: "7", name: "Diseño y Evaluación de Proyecto", time: "17:00", day: 5, duration: 2, link: "https://teams.microsoft.com/meet/266096719618997?p=SGWR0i7wtwal1LCv7T", type: "teams", color: "bg-indigo-500/10 border-indigo-500/20 text-indigo-600 dark:text-indigo-400", icon: MapPin, passcode: "Passcode: xv9t2Xd9" },
];

const DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];
const HOURS = ["17:00", "19:00"];

export function ClassSchedule() {
  return (
    <div className="w-full bg-background rounded-3xl border shadow-sm p-4 sm:p-6 md:p-8 overflow-hidden relative">
      {/* Decorative background element */}
      <div className="absolute top-0 right-0 -m-20 w-64 h-64 bg-primary/5 rounded-full blur-3xl pointer-events-none" />
      
      <div className="flex items-center gap-3 mb-6 sm:mb-8">
        <div className="p-2.5 sm:p-3 bg-primary/10 rounded-xl">
          <Clock className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight">Mi Horario</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">Clases y enlaces rápidos</p>
        </div>
      </div>

      <div className="overflow-x-auto pb-4">
        <div className="min-w-[800px]">
          {/* Header row (Days) */}
          <div className="grid grid-cols-6 gap-4 mb-4">
            <div className="w-full"></div> {/* Empty top-left cell */}
            {DAYS.map((day, i) => (
              <div key={day} className="text-center font-bold text-sm text-foreground/70 uppercase tracking-widest border-b pb-2">
                {day}
              </div>
            ))}
          </div>

          {/* Time Rows */}
          {HOURS.map((hour, rowIdx) => (
            <div key={hour} className="grid grid-cols-6 gap-4 mb-4 relative z-10">
              <div className="flex items-center justify-end pr-4 text-sm font-medium text-muted-foreground">
                <span className="bg-muted px-3 py-1 rounded-full text-xs shadow-sm shadow-black/5">{hour}</span>
              </div>
              
              {DAYS.map((_, colIdx) => {
                const dayNum = colIdx + 1; // 1 = Monday
                const item = SCHEDULE.find(s => s.day === dayNum && s.time === hour);

                return (
                  <div key={`${dayNum}-${hour}`} className="min-h-[140px] relative">
                    {item ? (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: rowIdx * 0.1 + colIdx * 0.05 }}
                        className={`absolute inset-0 p-4 rounded-2xl border backdrop-blur-sm shadow-sm flex flex-col justify-between group transition-all duration-300 hover:shadow-md hover:scale-[1.02] ${item.color}`}
                      >
                        <div>
                          <div className="flex justify-between items-start mb-2">
                            <span className="text-[10px] uppercase font-bold tracking-wider opacity-70">
                              {item.duration}H
                            </span>
                            <item.icon className="w-4 h-4 opacity-70" />
                          </div>
                          <h3 className="font-semibold text-sm leading-tight group-hover:text-foreground transition-colors">
                            {item.name}
                          </h3>
                          {item.passcode && (
                            <p className="mt-1 text-xs opacity-60 font-mono hidden group-hover:block transition-all">
                              {item.passcode}
                            </p>
                          )}
                        </div>

                        {item.type !== 'none' ? (
                          <a 
                            href={item.link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="mt-4 flex items-center justify-center gap-2 w-full py-2 rounded-lg bg-background/50 hover:bg-background/80 text-foreground text-xs font-medium transition-colors border border-transparent hover:border-border"
                          >
                            <Video className="w-3 h-3" />
                            Unirse ({item.type === 'zoom' ? 'Zoom' : 'Teams'})
                          </a>
                        ) : (
                          <div className="mt-4 flex items-center justify-center gap-2 w-full py-2 rounded-lg bg-background/20 text-xs font-medium opacity-50">
                            No disponible
                          </div>
                        )}
                      </motion.div>
                    ) : (
                      <div className="absolute inset-0 border border-dashed border-border/40 rounded-2xl flex flex-col items-center justify-center bg-muted/10 opacity-50">
                        <span className="w-1 h-1 bg-border rounded-full" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
