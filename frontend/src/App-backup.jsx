import React, { useState, useEffect } from 'react';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [kpis, setKpis] = useState(null);

  useEffect(() => {
    fetch('/dashboard/overview')
      .then(res => res.json())
      .then(data => setKpis(data.kpis))
      .catch(err => console.error("Could not fetch KPIs:", err));
  }, []);

  return (
    <div className="min-h-screen bg-slate-100 text-slate-800">
      {/* Top Header */}
      <header className="bg-[#0A192F] text-white border-b border-slate-700 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500 flex items-center justify-center font-bold text-slate-900">
              FLA
            </div>
            <div>
              <h1 className="font-extrabold text-lg tracking-wider">FIDELITY LIFE ASSURANCE</h1>
              <p className="text-xs text-slate-400">NEXA AI Fraud Detection and Claims Risk Assessment Platform</p>
            </div>
          </div>
          <div className="text-xs text-slate-300">
            AI Engine: <span className="font-semibold text-emerald-400">v1.2-ensemble</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto p-6 space-y-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h2 className="text-2xl font-bold text-slate-900">Executive Claims & Fraud Risk Intelligence</h2>
          <p className="text-sm text-slate-500">Continuous AI evaluation of policy inception, duplicate claims, and OCR document forensics.</p>
        </div>

        {kpis && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <span className="text-xs font-semibold uppercase text-slate-500">Total Claims</span>
              <p className="text-2xl font-bold text-slate-900">{kpis.total_claims_received}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <span className="text-xs font-semibold uppercase text-slate-500">AI Analysed</span>
              <p className="text-2xl font-bold text-purple-700">{kpis.claims_analysed_by_ai}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <span className="text-xs font-semibold uppercase text-slate-500">Critical Risk</span>
              <p className="text-2xl font-bold text-red-600">{kpis.critical_risk_claims}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <span className="text-xs font-semibold uppercase text-slate-500">Losses Prevented</span>
              <p className="text-2xl font-bold text-emerald-600">${kpis.prevented_fraud_losses_usd.toLocaleString()}</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
