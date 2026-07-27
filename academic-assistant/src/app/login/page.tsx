'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Lock, ArrowRight, ShieldCheck } from 'lucide-react';

export default function LoginPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });

      if (res.ok) {
        router.push('/');
        router.refresh();
      } else {
        const data = await res.json();
        setError(data.error  'Contraseña incorrecta');
      }
    } catch (err) {
      setError('Error de conexión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4 relative overflow-hidden">
      {/* Background Effect */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-zinc-900 via-zinc-950 to-zinc-950 pointer-events-none"></div>
      
      <div className="w-full max-w-md relative z-10">
        <div className="bg-zinc-900/50 backdrop-blur-xl border border-white/10 p-8 rounded-3xl shadow-2xl overflow-hidden relative">
          {/* Decorative glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-48 bg-blue-500/20 rounded-full blur-[60px] pointer-events-none"></div>
          
          <div className="flex flex-col items-center mb-8 text-center relative z-10">
            <div className="w-16 h-16 bg-gradient-to-tr from-blue-600 to-indigo-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-blue-500/20">
              <ShieldCheck className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2 tracking-tight">Acceso Restringido</h1>
            <p className="text-zinc-400">Introduce la contraseña maestra para acceder a tu Asistente Académico.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6 relative z-10">
            <div className="space-y-2">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-zinc-500" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 bg-zinc-950/50 border border-white/10 rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all duration-300"
                  placeholder="Contraseña"
                  required
                />
              </div>
              {error && (
                <p className="text-red-400 text-sm mt-2 text-center animate-pulse">{error}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full relative group bg-white text-zinc-950 font-semibold py-3 px-4 rounded-xl transition-all duration-300 hover:bg-zinc-200 active:scale-[0.98] disabled:opacity-70 disabled:active:scale-100 flex items-center justify-center overflow-hidden"
            >
              <span className="relative z-10 flex items-center gap-2">
                {loading ? 'Verificando...' : 'Desbloquear'}
                {!loading && <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />}
              </span>
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-indigo-500/10 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
