import './globals.css'
import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Bloomberg + Palantir Quant Terminal',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <nav style={{ padding: '24px', borderBottom: '1px solid var(--border-glass)', display: 'flex', gap: '24px', alignItems: 'center' }}>
          <h2 style={{ color: 'var(--cyan-primary)', marginRight: 'auto', fontSize: '1.2rem', letterSpacing: '2px' }}>MIROFISH TERMINAL</h2>
          <Link href="/" style={{ color: 'white', textDecoration: 'none', opacity: 0.8 }}>Dashboard</Link>
          <Link href="/trades" style={{ color: 'white', textDecoration: 'none', opacity: 0.8 }}>Trade Logger</Link>
          <Link href="/performance" style={{ color: 'white', textDecoration: 'none', opacity: 0.8 }}>Performance</Link>
        </nav>
        {children}
      </body>
    </html>
  )
}
