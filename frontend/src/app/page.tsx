'use client'
import { useQuery } from '@tanstack/react-query'
import { Users, FileText, FlaskConical, Zap, TrendingUp, Map } from 'lucide-react'
import { api } from '@/lib/api'

const KPICard = ({ icon: Icon, label, value, color }: any) => (
  <div className="card flex items-center gap-4">
    <div className={`p-3 rounded-lg ${color}`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <div>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value ?? '—'}</p>
    </div>
  </div>
)

export default function OverviewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['overview'],
    queryFn: () => api('/api/overview'),
    refetchInterval: 60000,
  })

  const { data: topHCPs } = useQuery({
    queryKey: ['top-hcps'],
    queryFn: () => api('/api/scoring/top?n=5'),
  })

  const { data: triggerSummary } = useQuery({
    queryKey: ['trigger-summary'],
    queryFn: () => api('/api/intelligence/triggers/summary'),
  })

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Executive Overview</h1>
        <p className="text-gray-500 mt-1">Real-time oncology commercial intelligence</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <KPICard icon={Users} label="HCPs" value={data?.hcp_count?.toLocaleString()} color="bg-blue-500" />
        <KPICard icon={FileText} label="Publications" value={data?.publication_count?.toLocaleString()} color="bg-purple-500" />
        <KPICard icon={FlaskConical} label="Active Trials" value={data?.trial_count?.toLocaleString()} color="bg-green-500" />
        <KPICard icon={Zap} label="Pending Triggers" value={data?.pending_triggers?.toLocaleString()} color="bg-amber-500" />
        <KPICard icon={TrendingUp} label="Queued Messages" value={data?.unsent_messages?.toLocaleString()} color="bg-rose-500" />
        <KPICard icon={Map} label="Territories" value={data?.territories_covered?.toLocaleString()} color="bg-teal-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Top HCPs by Commercial Score</h2>
          <div className="space-y-3">
            {topHCPs?.map((hcp: any) => (
              <div key={hcp.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="font-medium text-sm">{hcp.name}</p>
                  <p className="text-xs text-gray-500">{hcp.specialty} · {hcp.state}</p>
                </div>
                <div className="text-right">
                  <span className="text-sm font-bold text-brand-600">{hcp.commercial_score?.toFixed(1)}</span>
                  {hcp.kol_tier && (
                    <span className="ml-2 badge bg-blue-50 text-blue-700">{hcp.kol_tier}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Trigger Events (Last 30 Days)</h2>
          <div className="space-y-3">
            {triggerSummary?.map((t: any) => (
              <div key={t.event_type} className="flex items-center justify-between">
                <span className="text-sm text-gray-700">{t.event_type.replace(/_/g, ' ')}</span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand-500 rounded-full"
                      style={{ width: `${Math.min((t.count / 100) * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium w-8 text-right">{t.count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
