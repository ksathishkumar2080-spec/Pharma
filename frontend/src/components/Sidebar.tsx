'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Users, Map, Zap, Search,
  MessageSquare, FlaskConical, FileText, Target, ChevronRight
} from 'lucide-react'
import { clsx } from 'clsx'

const NAV = [
  { href: '/',          label: 'Overview',      icon: LayoutDashboard },
  { href: '/hcps',      label: 'HCPs',          icon: Users },
  { href: '/territory', label: 'Territory',     icon: Map },
  { href: '/nba',       label: 'Next Best Action', icon: Target },
  { href: '/triggers',  label: 'Trigger Feed',  icon: Zap },
  { href: '/search',    label: 'Search',        icon: Search },
]

export default function Sidebar() {
  const path = usePathname()
  return (
    <aside className="w-56 bg-brand-900 text-white flex flex-col shrink-0">
      <div className="px-4 py-5 border-b border-white/10">
        <p className="text-xs font-semibold text-blue-200 uppercase tracking-wider">Oncology Intel OS</p>
        <p className="text-xs text-blue-300 mt-0.5">Commercial Intelligence</p>
      </div>
      <nav className="flex-1 p-3 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
              path === href
                ? 'bg-white/15 text-white font-medium'
                : 'text-blue-200 hover:bg-white/10 hover:text-white'
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        ))}
      </nav>
      <div className="p-4 border-t border-white/10 text-xs text-blue-300">
        Internal use only
      </div>
    </aside>
  )
}
