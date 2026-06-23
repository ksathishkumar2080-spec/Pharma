'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { api } from '@/lib/api'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<'publications' | 'hcps' | 'fulltext'>('publications')
  const [submitted, setSubmitted] = useState('')

  const { data: results, isLoading } = useQuery({
    queryKey: ['search', mode, submitted],
    queryFn: () => {
      if (mode === 'fulltext') return api(`/api/search/?q=${encodeURIComponent(submitted)}`)
      return api(`/api/semantic/${mode}?q=${encodeURIComponent(submitted)}`)
    },
    enabled: !!submitted,
  })

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-2xl font-bold">Intelligence Search</h1>

      <div className="card space-y-4">
        <div className="flex gap-2">
          {(['publications', 'hcps', 'fulltext'] as const).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                mode === m ? 'bg-brand-500 text-white border-brand-500' : 'border-gray-200 text-gray-600'
              }`}
            >
              {m === 'fulltext' ? 'Full-text' : m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>

        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm"
              placeholder={
                mode === 'hcps'
                  ? 'Search by research interest, e.g. "KRAS mutation lung cancer"'
                  : 'Search publications or news...'
              }
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && setSubmitted(query)}
            />
          </div>
          <button className="btn-primary" onClick={() => setSubmitted(query)}>Search</button>
        </div>
      </div>

      {isLoading && <p className="text-gray-400">Searching...</p>}

      <div className="space-y-3">
        {results?.map((r: any, i: number) => (
          <div key={i} className="card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-sm">{r.title || r.name || r.source?.title || 'Untitled'}</p>
                {r.journal && <p className="text-xs text-gray-500 mt-0.5">{r.journal}</p>}
                {r.specialty && <p className="text-xs text-gray-500 mt-0.5">{r.specialty} · {r.state}</p>}
              </div>
              {(r.similarity ?? r.relevance_score) !== undefined && (
                <span className="text-xs font-medium text-brand-600 shrink-0">
                  {((r.similarity ?? r.relevance_score) * 100).toFixed(0)}% match
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
