'use client';
import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const ANALYTICS_URL = process.env.NEXT_PUBLIC_ANALYTICS_URL || 'http://localhost:8003';

export default function AnalyticsPage() {
  const [funnel, setFunnel] = useState<any[]>([]);
  const [rates, setRates] = useState<any>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [feedbackSummary, setFeedbackSummary] = useState<any[]>([]);

  useEffect(() => {
    fetch(`${ANALYTICS_URL}/analytics/funnel/drop-off`).then(r => r.json()).then(setFunnel).catch(() => {});
    fetch(`${ANALYTICS_URL}/analytics/conversions/rates`).then(r => r.json()).then(setRates).catch(() => {});
    fetch(`${ANALYTICS_URL}/analytics/cohort/model-improvement-signals`).then(r => r.json()).then(setSignals).catch(() => {});
    fetch(`${ANALYTICS_URL}/analytics/feedback/summary`).then(r => r.json()).then(setFeedbackSummary).catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-8">
      <h1 className="text-2xl font-bold">Analytics & Feedback</h1>
      {rates && (
        <section>
          <h2 className="text-lg font-semibold mb-2">Message Conversion Rates</h2>
          <div className="grid grid-cols-3 gap-4">
            {['open_rate','reply_rate','meeting_rate'].map(k => (
              <div key={k} className="bg-white rounded-xl shadow p-4 text-center">
                <div className="text-3xl font-bold text-blue-600">{((rates[k]||0)*100).toFixed(1)}%</div>
                <div className="text-sm text-gray-500 mt-1 capitalize">{k.replace('_',' ')}</div>
              </div>
            ))}
          </div>
        </section>
      )}
      <section>
        <h2 className="text-lg font-semibold mb-2">Engagement Funnel</h2>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={funnel}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="stage" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#3b82f6" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>
      <section>
        <h2 className="text-lg font-semibold mb-2">Scoring Model Signals</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead><tr className="bg-gray-50">
              <th className="px-4 py-2 text-left">HCP</th>
              <th className="px-4 py-2 text-left">Tier</th>
              <th className="px-4 py-2 text-right">Score</th>
              <th className="px-4 py-2 text-right">Reply%</th>
              <th className="px-4 py-2 text-left">Signal</th>
            </tr></thead>
            <tbody>{signals.slice(0,20).map((r,i)=>(
              <tr key={i} className="border-t">
                <td className="px-4 py-2">{r.name}</td>
                <td className="px-4 py-2">{r.kol_tier}</td>
                <td className="px-4 py-2 text-right font-mono">{r.influence_score?.toFixed(1)}</td>
                <td className="px-4 py-2 text-right font-mono">{r.actual_reply_rate_pct}%</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    r.signal==='underrated'?'bg-green-100 text-green-700':
                    r.signal==='overrated'?'bg-red-100 text-red-700':'bg-gray-100 text-gray-600'
                  }`}>{r.signal}</span>
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
