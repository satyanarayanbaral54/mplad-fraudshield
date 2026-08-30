import React, { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { projectsApi, surveysApi, triggerSurvey } from '../api/apiClient';

const scoreColor = (score) => {
  if (score < 2) return 'text-red-300 bg-red-500/15 border-red-400/25';
  if (score < 3) return 'text-orange-300 bg-orange-500/15 border-orange-400/25';
  if (score < 4) return 'text-yellow-200 bg-yellow-500/15 border-yellow-400/25';
  return 'text-emerald-300 bg-emerald-500/15 border-emerald-400/25';
};

const stars = (score) => {
  const filled = Math.round(Number(score || 0));
  return `${'⭐'.repeat(filled)}${'☆'.repeat(Math.max(0, 5 - filled))}`;
};

function KpiCard({ label, value, subtitle }) {
  return (
    <div className="rounded-lg border border-white/10 bg-slate-950/60 p-5 shadow-2xl shadow-black/20 backdrop-blur-xl">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-black text-white">{value}</p>
      {subtitle ? <p className="mt-2 text-xs text-slate-500">{subtitle}</p> : null}
    </div>
  );
}

export default function SurveyDashboard() {
  const [projects, setProjects] = useState([]);
  const [surveyByProject, setSurveyByProject] = useState({});
  const [loading, setLoading] = useState(true);
  const [sendingId, setSendingId] = useState(null);
  const [toast, setToast] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      const projectRes = await projectsApi.list({ limit: 500 });
      const projectRows = projectRes.data || [];
      setProjects(projectRows);

      const surveyEntries = await Promise.all(
        projectRows.map((project) =>
          surveysApi.getForProject(project.id)
            .then((response) => [project.id, response.data])
            .catch(() => [project.id, null])
        )
      );
      setSurveyByProject(Object.fromEntries(surveyEntries));
    } catch (err) {
      console.error('Failed to load survey dashboard', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const rows = useMemo(() => {
    return projects.map((project) => {
      const survey = surveyByProject[project.id] || {};
      const responses = survey.all_responses || [];
      return {
        project,
        sent: Number(survey.sent_count || 0),
        responses: Number(survey.response_count || responses.length || 0),
        responseRate: Number(survey.response_rate || 0),
        avgScore: Number(survey.avg_satisfaction || 0),
        aware: Number(survey.aware_citizens_pct || 0),
        responsesRaw: responses,
      };
    }).sort((a, b) => a.aware - b.aware || b.responses - a.responses);
  }, [projects, surveyByProject]);

  const kpis = useMemo(() => {
    const totalSent = rows.reduce((sum, row) => sum + row.sent, 0);
    const totalResponses = rows.reduce((sum, row) => sum + row.responses, 0);
    const avgResponseRate = rows.length ? rows.reduce((sum, row) => sum + row.responseRate, 0) / rows.length : 0;
    const scoredRows = rows.filter((row) => row.avgScore > 0);
    const avgSatisfaction = scoredRows.length ? scoredRows.reduce((sum, row) => sum + row.avgScore, 0) / scoredRows.length : 0;
    return { totalSent, totalResponses, avgResponseRate, avgSatisfaction };
  }, [rows]);

  const distribution = useMemo(() => {
    const buckets = [1, 2, 3, 4, 5].map((score) => ({ score: `${score}★`, count: 0 }));
    rows.forEach((row) => {
      row.responsesRaw.forEach((response) => {
        const score = Math.round(Number(response.satisfaction_score || response.quality_score || 0));
        if (score >= 1 && score <= 5) buckets[score - 1].count += 1;
      });
    });
    return buckets;
  }, [rows]);

  const lowAwarenessCount = rows.filter((row) => row.aware < 20).length;

  const handleSendSurvey = async (projectId) => {
    try {
      setSendingId(projectId);
      const result = await triggerSurvey(projectId);
      setToast(`Survey dispatched to ${result.phones_queued || 0} citizens`);
      await loadData();
    } catch (err) {
      console.error('Survey dispatch failed', err);
      setToast('Survey dispatch failed');
    } finally {
      setSendingId(null);
      window.setTimeout(() => setToast(''), 4000);
    }
  };

  return (
    <div className="space-y-6">
      {toast ? <div className="fixed right-6 top-6 z-[1000] rounded-lg border border-cyan-400/30 bg-slate-950 px-4 py-3 text-sm font-bold text-cyan-100 shadow-2xl">{toast}</div> : null}

      <div>
        <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-300">Ground Truth Layer</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-white">Citizen Survey Intelligence</h1>
        <p className="mt-2 text-sm text-slate-400">Survey response health, citizen awareness, and satisfaction signals by project.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Total Surveys Sent" value={kpis.totalSent} />
        <KpiCard label="Total Responses" value={kpis.totalResponses} />
        <KpiCard label="Avg Response Rate" value={`${kpis.avgResponseRate.toFixed(1)}%`} />
        <KpiCard label="Avg Satisfaction" value={`${kpis.avgSatisfaction.toFixed(1)}/5`} subtitle={stars(kpis.avgSatisfaction)} />
      </div>

      <div className="rounded-lg border border-red-400/30 bg-red-500/15 p-4 text-sm font-bold text-red-100 shadow-xl">
        🚨 {lowAwarenessCount} projects have &lt;20% citizen awareness — possible ghost projects. Recommend field audit.
      </div>

      <div className="overflow-hidden rounded-lg border border-white/10 bg-slate-950/60 shadow-2xl shadow-black/25 backdrop-blur-xl">
        <div className="border-b border-slate-800 p-5">
          <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-white">Projects with Survey Data</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1040px] text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950 text-slate-400">
              <tr>
                <th className="p-4">Project</th>
                <th className="p-4">MP</th>
                <th className="p-4">District</th>
                <th className="p-4">Sent</th>
                <th className="p-4">Responses</th>
                <th className="p-4">Response Rate</th>
                <th className="p-4">Avg Score</th>
                <th className="p-4">Stars</th>
                <th className="p-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70 text-slate-300">
              {loading ? (
                <tr><td colSpan="9" className="p-8 text-center text-slate-500">Loading survey intelligence...</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan="9" className="p-8 text-center text-slate-500">No projects available.</td></tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.project.id} className="transition hover:bg-white/[0.04]">
                    <td className="max-w-[320px] p-4 font-bold text-white">{row.project.title}</td>
                    <td className="p-4">{row.project.mp_name || 'N/A'}</td>
                    <td className="p-4">{row.project.district || 'N/A'}</td>
                    <td className="p-4 font-mono">{row.sent}</td>
                    <td className="p-4 font-mono">{row.responses}</td>
                    <td className="p-4 font-mono">{row.responseRate.toFixed(1)}%</td>
                    <td className="p-4">
                      <span className={`rounded-full border px-2.5 py-1 font-black ${scoreColor(row.avgScore)}`}>
                        {row.avgScore.toFixed(1)}
                      </span>
                    </td>
                    <td className="p-4 text-sm">{stars(row.avgScore)}</td>
                    <td className="p-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleSendSurvey(row.project.id)}
                        disabled={sendingId === row.project.id}
                        className="inline-flex h-9 items-center rounded-lg border border-cyan-400/25 bg-cyan-400/10 px-3 text-xs font-bold text-cyan-100 transition hover:bg-cyan-400/20 disabled:opacity-60"
                      >
                        {sendingId === row.project.id ? 'Sending...' : 'Send Survey'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <section className="rounded-lg border border-white/10 bg-slate-950/60 p-5 shadow-2xl shadow-black/25 backdrop-blur-xl">
        <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-white">Satisfaction Score Distribution</h2>
        <div className="mt-4 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={distribution} margin={{ top: 12, right: 24, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="score" stroke="#94a3b8" tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: '#020617', border: '1px solid #334155', borderRadius: 8, color: '#ffffff' }}
                itemStyle={{ color: '#ffffff' }}
                labelStyle={{ color: '#ffffff', fontWeight: 600 }}
              />
              <Bar dataKey="count" fill="#38bdf8" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
