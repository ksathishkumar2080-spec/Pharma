'use client'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api, apiPost } from '@/lib/api'
import { MessageSquare, FlaskConical, FileText, Zap, Users } from 'lucide-react'

export default function HCPDetailPage({ params }: { params: { id: string } }) {
  const { id } = params
  const [channel, setChannel] = useState('linkedin')
  const [contextNotes, setContextNotes] = useState('')

  const { data: hcp } = useQuery({ queryKey: ['hcp', id], queryFn: () => api(`/api/hcps/${id}`) })
  const { data: nba } = useQuery({ queryKey: ['nba', id], queryFn: () => api(`/api/territory/nba?limit=1`) })
  const { data: network } = useQuery({ queryKey: ['network', id], queryFn: () => api(`/api/territory/network/${id}`) })

  const messageMutation = useMutation({
    mutationFn: () => apiPost('/messaging/generate', { hcp_id: id, channel, context_notes: contextNotes }),
  })

  if (!hcp) return <div className="p-8 text-gray-400">Loading...</div>

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{hcp.full_name}</h1>
          <p className="text-gray-500">{hcp.specialty} · {hcp.state}</p>
        </div>
        <div className="flex gap-2">
          {hcp.kol_tier && (
            <span className="badge bg-purple-100 text-purple-700 text-sm px-3 py-1">{hcp.kol_tier} KOL</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center">
          <p className="text-3xl font-bold text-brand-600">{hcp.commercial_score?.toFixed(1)}</p>
          <p className="text-sm text-gray-500 mt-1">Commercial Score</p>
        </div>
        <div className="card text-center">
          <p className="text-3xl font-bold text-purple-600">{hcp.opportunity_score?.toFixed(1)}</p>
          <p className="text-sm text-gray-500 mt-1">Opportunity Score</p>
        </div>
        <div className="card text-center">
          <p className="text-3xl font-bold text-green-600">{hcp.influence_score?.toFixed(1)}</p>
          <p className="text-sm text-gray-500 mt-1">Influence Score</p>
        </div>
      </div>

      {/* Referral network */}
      {network?.network?.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2"><Users className="w-5 h-5" />Referral Network ({network.network.length} connections)</h2>
          <div className="flex flex-wrap gap-2">
            {network.network.slice(0, 12).map((n: any) => (
              <span key={n.id} className="badge bg-gray-100 text-gray-700">{n.name} ({n.hops === 1 ? 'direct' : `${n.hops} hops`})</span>
            ))}
          </div>
        </div>
      )}

      {/* Message generator */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2"><MessageSquare className="w-5 h-5" />Generate Outreach</h2>
        <div className="flex gap-3">
          {['linkedin', 'email', 'conversation_starter', 'follow_up'].map(ch => (
            <button
              key={ch}
              onClick={() => setChannel(ch)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                channel === ch ? 'bg-brand-500 text-white border-brand-500' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {ch.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
        <textarea
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          rows={2}
          placeholder="Additional context for the rep (optional)..."
          value={contextNotes}
          onChange={e => setContextNotes(e.target.value)}
        />
        <button
          className="btn-primary"
          onClick={() => messageMutation.mutate()}
          disabled={messageMutation.isPending}
        >
          {messageMutation.isPending ? 'Generating...' : 'Generate Message'}
        </button>

        {messageMutation.data && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg space-y-2">
            {messageMutation.data.subject && (
              <p className="text-sm font-medium">Subject: {messageMutation.data.subject}</p>
            )}
            <p className="text-sm whitespace-pre-wrap">{messageMutation.data.body}</p>
            {messageMutation.data.grammar_issues?.length > 0 && (
              <p className="text-xs text-amber-600">{messageMutation.data.grammar_issues.length} grammar suggestion(s) applied</p>
            )}
            {messageMutation.data.evidence_citations?.length > 0 && (
              <div className="mt-2">
                <p className="text-xs font-medium text-gray-500">Evidence Citations:</p>
                {messageMutation.data.evidence_citations.map((c: any, i: number) => (
                  <p key={i} className="text-xs text-gray-500">· {c.title} ({c.type})</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
