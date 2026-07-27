import { useQuery } from '@tanstack/react-query'
import { buildApiUrl } from '@/lib/api'

export function useMetrics(
  days: number = 365, 
  botId: number  null = null,
  accountLogin: string  null = null,
  serverName: string  null = null
) {
  return useQuery({
    queryKey: ['metrics', days, botId, accountLogin, serverName],
    queryFn: async () => {
      const safeDays = Number.isFinite(days) && days > 0 ? Math.floor(days) : undefined
      const res = await fetch(
        buildApiUrl('/metrics', { 
          days: safeDays, 
          bot_id: botId ?? undefined,
          account_login: accountLogin ?? undefined,
          server_name: serverName ?? undefined
        })
      )
      if (!res.ok) throw new Error('API Sync Failed')
      return res.json()
    },
    refetchInterval: 30000,
    staleTime: 20000,
    refetchOnWindowFocus: false,
  })
}

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const res = await fetch(buildApiUrl('/accounts'))
      if (!res.ok) throw new Error('Failed to fetch accounts')
      return res.json()
    },
    refetchInterval: 60000,
    staleTime: 30000,
    refetchOnWindowFocus: false,
  })
}

export function useLivePositions(accountLogin: string  null = null, serverName: string  null = null) {
  return useQuery({
    queryKey: ['live', accountLogin, serverName],
    queryFn: async () => {
      const res = await fetch(buildApiUrl('/live', {
        account_login: accountLogin ?? undefined,
        server_name: serverName ?? undefined,
      }))
      if (!res.ok) throw new Error('MT5 Node Offline')
      return res.json()
    },
    refetchInterval: 5000,
  })
}
