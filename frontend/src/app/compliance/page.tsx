'use client';
import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function CompliancePage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [verifyId, setVerifyId] = useState('');
  const [report, setReport] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_URL}/compliance/audit-log?limit=50`)
      .then(r => r.json()).then(setLogs);
  }, []);

  const verify = async () => {
    if (!verifyId) return;
    const r = await fetch(`${API_URL}/compliance/verify-message/${verifyId}`, { method: 'POST' });
    setReport(await r.json());
  };

  return (
    <div className="p-6 space-y-8">
      <h1 className="text-2xl font-bold">Compliance & Audit</h1>
      <section className="bg-white rounded-xl shadow p-4">
        <h2 className="text-lg font-semibold mb-3">Citation Verifier</h2>
        <div className="flex gap-2">
          <input className="border rounded px-3 py-1.5 flex-1 text-sm" placeholder="Message ID"
            value={verifyId} onChange={e => setVerifyId(e.target.value)} />
          <button onClick={verify} className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm">Verify</button>
        </div>
        {report && (
          <div className="mt-4 space-y-2">
            <div className={`inline-flex px-3 py-1 rounded text-sm font-medium ${
              report.compliant ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}>
              {report.compliant ? 'Compliant' : 'Non-Compliant'} - Score: {(report.score * 100).toFixed(0)}%
            </div>
            <div className="text-sm text-gray-600">
              {report.verified}/{report.total_claims} claims verified, {report.flagged} flagged
            </div>
          </div>
        )}
      </section>
      <section>
        <h2 className="text-lg font-semibold mb-2">API Audit Log</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead><tr className="bg-gray-50">
              <th className="px-3 py-2 text-left">Time</th>
              <th className="px-3 py-2 text-left">User</th>
              <th className="px-3 py-2 text-left">Method</th>
              <th className="px-3 py-2 text-left">Path</th>
              <th className="px-3 py-2 text-right">Status</th>
              <th className="px-3 py-2 text-right">ms</th>
            </tr></thead>
            <tbody>{logs.map((r, i) => (
              <tr key={i} className="border-t font-mono">
                <td className="px-3 py-1.5">{new Date(r.created_at).toLocaleString()}</td>
                <td className="px-3 py-1.5">{r.user_id}</td>
                <td className="px-3 py-1.5"><span className="bg-gray-100 px-1 rounded">{r.method}</span></td>
                <td className="px-3 py-1.5 text-blue-700">{r.path}</td>
                <td className="px-3 py-1.5 text-right"><span className={r.status_code < 400 ? 'text-green-600' : 'text-red-600'}>{r.status_code}</span></td>
                <td className="px-3 py-1.5 text-right">{r.duration_ms}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
