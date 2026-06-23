'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'motion/react';

const NAV = [
  { href: '/',              label: 'Overview',          icon: 'Home' },
  { href: '/hcps',          label: 'HCPs',              icon: 'Users' },
  { href: '/graph',         label: 'Knowledge Graph',   icon: 'Network' },
  { href: '/territory',     label: 'Territory',         icon: 'Map' },
  { href: '/triggers',      label: 'Triggers',          icon: 'Zap' },
  { href: '/nba',           label: 'Next Best Actions', icon: 'Target' },
  { href: '/search',        label: 'Search',            icon: 'Search' },
  { href: '/orchestration', label: 'Orchestration',     icon: 'Cpu' },
  { href: '/analytics',     label: 'Analytics',         icon: 'BarChart2' },
  { href: '/compliance',    label: 'Compliance',        icon: 'Shield' },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 min-h-screen bg-gray-900 border-r border-gray-800 flex flex-col py-5 px-3">
      <div className="px-2 mb-6">
        <div className="text-blue-400 font-bold text-base">Oncology OS</div>
        <div className="text-gray-600 text-xs mt-0.5">Intelligence Platform</div>
      </div>
      <nav className="space-y-0.5 flex-1">
        {NAV.map(({ href, label }) => {
          const active = href === '/' ? path === href : path.startsWith(href);
          return (
            <Link key={href} href={href}>
              <motion.div whileHover={{ x: 3 }} transition={{ duration: 0.15 }}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors ${
                  active ? 'bg-blue-600/20 text-blue-300 font-medium' : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}>
                <span className="truncate flex-1">{label}</span>
                {active && <motion.span layoutId="dot" className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />}
              </motion.div>
            </Link>
          );
        })}
      </nav>
      <div className="px-3 pt-4 border-t border-gray-800 mt-4">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-gray-500">Pipeline running</span>
        </div>
      </div>
    </aside>
  );
}
