'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const nav = [
  { href: '/', label: 'Overview' },
  { href: '/hcps', label: 'HCPs' },
  { href: '/territory', label: 'Territory' },
  { href: '/triggers', label: 'Triggers' },
  { href: '/nba', label: 'Next Best Actions' },
  { href: '/search', label: 'Search' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/compliance', label: 'Compliance' },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-52 min-h-screen bg-gray-900 text-white flex flex-col py-6 px-4">
      <div className="text-lg font-bold mb-8 text-blue-400">Oncology OS</div>
      <nav className="space-y-1">
        {nav.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
              path === href
                ? 'bg-blue-600 text-white'
                : 'text-gray-300 hover:bg-gray-700'
            }`}
          >
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
