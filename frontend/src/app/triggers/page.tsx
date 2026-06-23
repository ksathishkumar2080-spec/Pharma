'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Zap } from 'lucide-react'

const EVENT_COLORS: Record<string, string> = {
  new_publication: 'bg-blue-100 text-blue-700',
  trial_enrollment_opened: 'bg-green-100 text-green-700',
  guideline_update: 'bg-purple-100 text-purple-700',
  competitor_drug_approved: 'bg-red-100 text-red-700',
  conference_presentation: 'bg-amber-100 text-amber-700',
  institution_change: 'bg-teal-100 text-teal-700',
  grant_awarded: 'bg-indigo-100 text-indigo-700',
}

export default function TriggersPage() {
  const { data: triggers, isLoading } = useQuery({
    queryKey: ['triggers'],
    queryFn: () => api('/api/triggers/?limit=100'),
    refetchInterval: 30000,
  })

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center gap-3">
        <Zap className="w-6 h-6 text-amber-500" />
        <h1 className="text-2xl font-bold">Buying Signal & Trigger Feed</h1>
      </div>

      <div className="space-y-3">
        {isLoading && <p className="text-gray-400">Loading triggers...</p>}
        {triggers?.map((t: any) => (
          <div key={t.id} className="card flex items-start gap-4">
            <span className={`badge mt-0.5 ${
              EVENT_COLORS[t.event_type] || 'bg-gray-100 text-gray-700'
            }`}>
              {t.event_type.replace(/_/g, ' ')}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{t.hcp_name}</p>
              <p className="text-xs text-gray-500 truncate">
                {t.occurred_at ? new Date(t.occurred_at).toLocaleDateString() : 'Unknown date'}
              </p>
            </div>
            {!t.processed && (
              <span className="badge bg-amber-50 text-amber-600 text-xs">New</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
