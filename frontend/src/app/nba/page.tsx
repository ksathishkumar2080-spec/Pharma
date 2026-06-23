'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useState } from 'react'
import Link from 'next/link'

const URGENCY_STYLES: Record<string, string> = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-gray-100 text-gray-600',
}

const ACTION_ICONS: Record<string, string> = {
  send_linkedin: '💼',
  send_email: '📧',
  schedule_call: '📞',
  invite_to_advisory: '🎯',
  share_data: '📊',
  trial_referral: '🔬',
  no_action: '⏸',
}

export default function NBAPage() {
  const [state, setState] = useState('')

  const { data: actions, isLoading } = useQuery({
    queryKey: ['nba', state],
    queryFn: () => api(`/api/territory/nba${state ? `?state=${state}` : ''}`),
    refetchInterval: 120000,
  })

  const high = actions?.filter((a: any) => a.urgency === 'high') || []
  const medium = actions?.filter((a: any) => a.urgency === 'medium') || []
  const low = actions?.filter((a: any) => a.urgency === 'low') || []

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Next Best Action Queue</h1>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">Filter by state:</label>
          <input
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-20"
            placeholder="e.g. CA"
            value={state}
            onChange={e => setState(e.target.value.toUpperCase())}
            maxLength={2}
          />
        </div>
      </div>

      {isLoading && <p className="text-gray-400">Computing actions...</p>}

      {[{label: 'High Priority', items: high, color: 'border-l-red-400'},
        {label: 'Medium Priority', items: medium, color: 'border-l-amber-400'},
        {label: 'Low Priority', items: low, color: 'border-l-gray-300'}].map(group => (
        <div key={group.label}>
          <h2 className="text-sm font-semibold text-gray-500 mb-2">{group.label} ({group.items.length})</h2>
          <div className="space-y-2">
            {group.items.map((action: any) => (
              <div key={action.hcp_id} className={`card border-l-4 ${group.color} py-4`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{ACTION_ICONS[action.action] || '▶'}</span>
                      <Link href={`/hcps/${action.hcp_id}`} className="font-medium text-sm hover:text-brand-600">
                        {action.hcp_name}
                      </Link>
                      <span className={`badge ${URGENCY_STYLES[action.urgency]}`}>{action.urgency}</span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      <span className="font-medium">{action.action.replace(/_/g, ' ')}</span>
                      {' — '}{action.rationale}
                    </p>
                    {action.suggested_talking_points?.length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {action.suggested_talking_points.map((tp: string, i: number) => (
                          <li key={i} className="text-xs text-gray-500">· {tp}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <span className="text-sm font-bold text-brand-600 shrink-0">{action.commercial_score?.toFixed(1)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
