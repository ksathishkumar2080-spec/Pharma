'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import Link from 'next/link'

const KOL_COLORS: Record<string, string> = {
  national: 'bg-purple-100 text-purple-700',
  regional: 'bg-blue-100 text-blue-700',
  local: 'bg-green-100 text-green-700',
  emerging: 'bg-amber-100 text-amber-700',
}

export default function HCPsPage() {
  const [specialty, setSpecialty] = useState('')
  const [state, setState] = useState('')
  const [kolTier, setKolTier] = useState('')
  const [minScore, setMinScore] = useState(0)

  const params = new URLSearchParams()
  if (specialty) params.set('specialty', specialty)
  if (state) params.set('state', state)
  if (kolTier) params.set('kol_tier', kolTier)
  if (minScore > 0) params.set('min_score', String(minScore))
  params.set('limit', '100')

  const { data: hcps, isLoading } = useQuery({
    queryKey: ['hcps', specialty, state, kolTier, minScore],
    queryFn: () => api(`/api/hcps/?${params.toString()}`),
  })

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-2xl font-bold">HCP Intelligence</h1>

      {/* Filters */}
      <div className="card">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Specialty</label>
            <input
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. Hematology"
              value={specialty}
              onChange={e => setSpecialty(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">State</label>
            <input
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. CA"
              value={state}
              onChange={e => setState(e.target.value.toUpperCase())}
              maxLength={2}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">KOL Tier</label>
            <select
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={kolTier}
              onChange={e => setKolTier(e.target.value)}
            >
              <option value="">All</option>
              <option value="national">National</option>
              <option value="regional">Regional</option>
              <option value="local">Local</option>
              <option value="emerging">Emerging</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Min Score</label>
            <input
              type="number"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              min={0} max={100}
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left text-xs font-medium text-gray-500 px-6 py-3">Name</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Specialty</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">State</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">KOL Tier</th>
              <th className="text-right text-xs font-medium text-gray-500 px-6 py-3">Score</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {isLoading ? (
              <tr><td colSpan={6} className="text-center py-8 text-gray-400">Loading...</td></tr>
            ) : hcps?.map((hcp: any) => (
              <tr key={hcp.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-3 font-medium text-sm">{hcp.name}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{hcp.specialty}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{hcp.state}</td>
                <td className="px-4 py-3">
                  {hcp.kol_tier && (
                    <span className={`badge ${KOL_COLORS[hcp.kol_tier] || 'bg-gray-100 text-gray-600'}`}>
                      {hcp.kol_tier}
                    </span>
                  )}
                </td>
                <td className="px-6 py-3 text-right">
                  <span className="text-sm font-bold text-brand-600">{hcp.commercial_score?.toFixed(1)}</span>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/hcps/${hcp.id}`} className="text-gray-400 hover:text-gray-600">
                    <ChevronRight className="w-4 h-4" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
