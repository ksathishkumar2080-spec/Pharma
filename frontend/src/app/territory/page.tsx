'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useState } from 'react'

function ScoreBar({ value, max = 100 }: { value: number; max?: number }) {
  return (
    <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
      <div
        className="h-full bg-brand-500 rounded-full"
        style={{ width: `${Math.min((value / max) * 100, 100)}%` }}
      />
    </div>
  )
}

export default function TerritoryPage() {
  const [selectedState, setSelectedState] = useState<string | null>(null)

  const { data: territories } = useQuery({
    queryKey: ['territories'],
    queryFn: () => api('/api/territory/'),
  })

  const { data: accounts } = useQuery({
    queryKey: ['territory-accounts', selectedState],
    queryFn: () => api(`/api/territory/${selectedState}/accounts`),
    enabled: !!selectedState,
  })

  const maxScore = Math.max(...(territories?.map((t: any) => t.territory_opportunity_score) || [1]))

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-2xl font-bold">Territory Opportunity Engine</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Territory Scores</h2>
          <div className="space-y-3 max-h-[600px] overflow-y-auto">
            {territories?.map((t: any) => (
              <div
                key={t.state}
                className={`p-3 rounded-lg cursor-pointer transition-colors ${
                  selectedState === t.state ? 'bg-brand-50 border border-brand-200' : 'hover:bg-gray-50'
                }`}
                onClick={() => setSelectedState(t.state)}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">{t.state}</span>
                  <span className="text-sm font-bold text-brand-600">{t.territory_opportunity_score.toFixed(1)}</span>
                </div>
                <ScoreBar value={t.territory_opportunity_score} max={maxScore} />
                <div className="flex gap-3 mt-1 text-xs text-gray-500">
                  <span>{t.hcp_count} HCPs</span>
                  <span>{t.kol_count} KOLs</span>
                  <span>{t.active_trials} trials</span>
                  <span>{t.recent_triggers} triggers</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">
            {selectedState ? `Top Accounts — ${selectedState}` : 'Select a territory'}
          </h2>
          {accounts ? (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {accounts.map((a: any) => (
                <div key={a.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div>
                    <p className="text-sm font-medium">{a.name}</p>
                    <p className="text-xs text-gray-500">{a.specialty} · {a.institution || 'Unknown institution'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-brand-600">{a.commercial_score?.toFixed(1)}</p>
                    <p className="text-xs text-amber-600">{a.recent_triggers} triggers</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-sm">Click a state to see top accounts</p>
          )}
        </div>
      </div>
    </div>
  )
}
