import type { Metadata } from 'next'
import './globals.css'
import Sidebar from '@/components/Sidebar'
import Providers from '@/components/Providers'

export const metadata: Metadata = {
  title: 'Oncology Intelligence OS',
  description: 'Internal intelligence platform for oncology commercial teams',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto bg-gray-50">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  )
}
