'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useEffect } from 'react'

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10000,
        refetchOnWindowFocus: false,
      },
    },
  }))

  useEffect(() => {
    // Only register the service worker in production. In development,
    // unregister any previously registered service workers to avoid
    // cached chunks interfering with Next.js dev HMR.
    if (process.env.NODE_ENV === 'production' && typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js')
        .then((reg) => console.log('ServiceWorker registered:', reg))
        .catch((err) => console.warn('SW registration failed:', err))
    } else if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations()
        .then((regs) => regs.forEach((reg) => reg.unregister().then(() => console.log('SW unregistered in dev:', reg))))
        .catch((err) => console.warn('SW unregister failed:', err))
    }
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
