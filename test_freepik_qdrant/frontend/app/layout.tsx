import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Ad Generation Agent',
  description: 'AI-powered advertisement creation with live pipeline observability',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  )
}

