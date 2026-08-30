import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { projectsApi } from '../api/apiClient';
import RiskBadge from '../components/RiskBadge';

const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa',
  'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala',
  'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland',
  'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
  'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Delhi', 'Jammu and Kashmir',
  'Ladakh', 'Puducherry', 'Chandigarh', 'Andaman and Nicobar Islands',
  'Dadra and Nagar Haveli and Daman and Diu', 'Lakshadweep',
];

const RISK_LEVELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const PAGE_SIZE = 20;

const riskTone = (score = 0) => {
  if (score >= 75) return 'bg-red-500';
  if (score >= 55) return 'bg-orange-500';
  if (score >= 30) return 'bg-yellow-400';
  return 'bg-emerald-500';
};

const flagIcon = (severity) => {
  if (severity === 'CRITICAL') return { text: 'CRITICAL', cls: 'text-red-400 font-bold text-[10px]' };
  if (severity === 'HIGH') return { text: 'HIGH', cls: 'text-orange-400 font-bold text-[10px]' };
  if (severity === 'MEDIUM') return { text: 'MED', cls: 'text-yellow-400 font-bold text-[10px]' };
  return { text: 'LOW', cls: 'text-emerald-400 font-bold text-[10px]' };
};

const amountLakhs = (project) => Number(project.allocated_amount || project.sanctioned_amount || 0) / 1e5;
const getWorkType = (project) => project.work_type || project.metadata_json?.work_type || project.description?.split(' ')[0] || 'General';
const getFinancialYear = (project) => {
  const rawDate = project.start_date || project.created_at || project.sanction_date;
  if (!rawDate) return 'Unknown';
  const date = new Date(rawDate);
  const year = date.getFullYear();
  const startYear = date.getMonth() >= 3 ? year : year - 1;
  return `${startYear}-${String(startYear + 1).slice(-2)}`;
};

const csvEscape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;

export default function ProjectList() {
  const [searchParams] = useSearchParams();
  const mpNameParam = searchParams.get('mp_name') || '';
  const [projects, setProjects] = useState([]);
  const [rowDetails, setRowDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [sortConfig, setSortConfig] = useState({ key: 'risk_score', direction: 'desc' });
  const [filters, setFilters] = useState({
    state: '',
    riskLevels: ['CRITICAL'],
    workType: '',
    financialYear: '',
    mpName: mpNameParam,
    text: '',
  });

  useEffect(() => {
    setFilters((current) => ({ ...current, mpName: mpNameParam }));
  }, [mpNameParam]);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoading(true);
        const response = await projectsApi.list({ limit: 1000 });
        setProjects(response.data || []);
      } catch (err) {
        console.error('Failed to load projects', err);
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const workTypes = useMemo(() => {
    return Array.from(new Set(projects.map(getWorkType).filter(Boolean))).sort();
  }, [projects]);

  const financialYears = useMemo(() => {
    return Array.from(new Set(projects.map(getFinancialYear))).filter((year) => year !== 'Unknown').sort().reverse();
  }, [projects]);

  const filteredProjects = useMemo(() => {
    const text = filters.text.trim().toLowerCase();
    const mpName = filters.mpName.trim().toLowerCase();

    return projects
      .filter((project) => !filters.state || project.state === filters.state)
      .filter((project) => filters.riskLevels.length === 0 || filters.riskLevels.includes(project.risk_level))
      .filter((project) => !filters.workType || getWorkType(project) === filters.workType)
      .filter((project) => !filters.financialYear || getFinancialYear(project) === filters.financialYear)
      .filter((project) => !mpName || (project.mp_name || '').toLowerCase().includes(mpName))
      .filter((project) => {
        if (!text) return true;
        return [project.title, project.mp_name, project.state, getWorkType(project)].some((value) =>
          String(value || '').toLowerCase().includes(text)
        );
      })
      .sort((a, b) => {
        const aValue = sortConfig.key === 'amount' ? amountLakhs(a) : a[sortConfig.key] || '';
        const bValue = sortConfig.key === 'amount' ? amountLakhs(b) : b[sortConfig.key] || '';
        const order = sortConfig.direction === 'asc' ? 1 : -1;
        if (typeof aValue === 'number' && typeof bValue === 'number') return (aValue - bValue) * order;
        return String(aValue).localeCompare(String(bValue)) * order;
      });
  }, [filters, projects, sortConfig]);

  const totalPages = Math.max(1, Math.ceil(filteredProjects.length / PAGE_SIZE));
  const pageProjects = filteredProjects.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const criticalCount = filteredProjects.filter((project) => project.risk_level === 'CRITICAL').length;

  useEffect(() => {
    setPage(1);
  }, [filters, sortConfig]);

  useEffect(() => {
    const missingRows = pageProjects.filter((project) => !rowDetails[project.id]);
    if (missingRows.length === 0) return;

    let cancelled = false;
    const loadDetails = async () => {
      try {
        setDetailLoading(true);
        const detailResponses = await Promise.all(
          missingRows.map((project) => projectsApi.get(project.id).catch(() => ({ data: project })))
        );
        if (cancelled) return;
        setRowDetails((current) => {
          const next = { ...current };
          detailResponses.forEach((response) => {
            next[response.data.id] = response.data;
          });
          return next;
        });
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    };

    loadDetails();
    return () => {
      cancelled = true;
    };
  }, [pageProjects, rowDetails]);

  const updateRiskLevel = (level) => {
    setFilters((current) => ({
      ...current,
      riskLevels: current.riskLevels.includes(level)
        ? current.riskLevels.filter((item) => item !== level)
        : [...current.riskLevels, level],
    }));
  };

  const setSort = (key) => {
    setSortConfig((current) => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }));
  };

  const exportCsv = () => {
    const headers = ['#', 'Project Name', 'MP', 'State', 'Work Type', 'Amount (INR L)', 'Risk Score', 'Risk Level', 'Flags'];
    const rows = filteredProjects.map((project, index) => {
      const detail = rowDetails[project.id] || project;
      const flags = (detail.flags || []).map((flag) => flag.flag_type).join('; ');
      return [
        index + 1,
        project.title,
        project.mp_name,
        project.state,
        getWorkType(project),
        amountLakhs(project).toFixed(2),
        Number(project.risk_score || 0).toFixed(0),
        project.risk_level,
        flags,
      ].map(csvEscape).join(',');
    });
    const blob = new Blob([[headers.map(csvEscape).join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'mplad-filtered-projects.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const sortableHeader = (key, label) => (
    <button type="button" onClick={() => setSort(key)} className="inline-flex items-center gap-1 text-left">
      {label}
      <span className="text-slate-500">{sortConfig.key === key ? (sortConfig.direction === 'desc' ? '↓' : '↑') : '↕'}</span>
    </button>
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-cyan-300">Forensic Project Registry</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">MPLAD Sanctioned Works</h1>
          <p className="mt-2 text-sm text-slate-400">
            Showing <span className="font-bold text-white">{filteredProjects.length}</span> of <span className="font-bold text-white">{projects.length}</span> projects | <span className="font-bold text-red-300">{criticalCount}</span> need immediate action
          </p>
        </div>
        <button
          type="button"
          onClick={exportCsv}
          className="h-10 rounded-lg border border-emerald-400/25 bg-emerald-500/15 px-4 text-xs font-bold text-emerald-100 transition hover:bg-emerald-500/25"
        >
          Export CSV
        </button>
      </div>

      <div className="rounded-lg border border-white/10 bg-slate-950/60 p-4 shadow-2xl shadow-black/25 backdrop-blur-xl">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Search
            <input
              value={filters.text}
              onChange={(event) => setFilters({ ...filters, text: event.target.value })}
              placeholder="Project, MP, state..."
              className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm normal-case tracking-normal text-white outline-none focus:border-cyan-400"
            />
          </label>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
            State
            <select value={filters.state} onChange={(event) => setFilters({ ...filters, state: event.target.value })} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm normal-case tracking-normal text-white outline-none focus:border-cyan-400">
              <option value="">All States</option>
              {INDIAN_STATES.map((state) => <option key={state} value={state}>{state}</option>)}
            </select>
          </label>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Work Type
            <select value={filters.workType} onChange={(event) => setFilters({ ...filters, workType: event.target.value })} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm normal-case tracking-normal text-white outline-none focus:border-cyan-400">
              <option value="">All Work Types</option>
              {workTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Financial Year
            <select value={filters.financialYear} onChange={(event) => setFilters({ ...filters, financialYear: event.target.value })} className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm normal-case tracking-normal text-white outline-none focus:border-cyan-400">
              <option value="">All Years</option>
              {financialYears.map((year) => <option key={year} value={year}>{year}</option>)}
            </select>
          </label>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
            MP Name
            <input
              value={filters.mpName}
              onChange={(event) => setFilters({ ...filters, mpName: event.target.value })}
              placeholder="Filter by MP"
              className="mt-2 h-10 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm normal-case tracking-normal text-white outline-none focus:border-cyan-400"
            />
          </label>
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Risk Level
            <div className="mt-2 grid grid-cols-2 gap-2">
              {RISK_LEVELS.map((level) => (
                <label key={level} className="flex h-10 items-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-2 text-[11px] normal-case tracking-normal text-slate-200">
                  <input type="checkbox" checked={filters.riskLevels.includes(level)} onChange={() => updateRiskLevel(level)} className="rounded border-slate-600 bg-slate-900 accent-cyan-400" />
                  {level}
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-white/10 bg-slate-950/60 shadow-2xl shadow-black/25 backdrop-blur-xl">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950 text-slate-400">
              <tr>
                <th className="p-4">#</th>
                <th className="p-4">{sortableHeader('title', 'Project Name')}</th>
                <th className="p-4">{sortableHeader('mp_name', 'MP')}</th>
                <th className="p-4">{sortableHeader('state', 'State')}</th>
                <th className="p-4">Work Type</th>
                <th className="p-4">{sortableHeader('amount', 'Amount (₹L)')}</th>
                <th className="p-4">{sortableHeader('risk_score', 'Risk Score')}</th>
                <th className="p-4">Risk Level</th>
                <th className="p-4">Flags {detailLoading ? <span className="text-cyan-300">loading</span> : null}</th>
                <th className="p-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70 text-slate-300">
              {loading ? (
                <tr><td colSpan="10" className="p-8 text-center text-slate-500">Loading project registry...</td></tr>
              ) : pageProjects.length === 0 ? (
                <tr><td colSpan="10" className="p-8 text-center text-slate-500">No projects match the current filters.</td></tr>
              ) : (
                pageProjects.map((project, index) => {
                  const score = Math.min(100, Math.max(0, Number(project.risk_score || 0)));
                  const detail = rowDetails[project.id] || project;
                  const flags = detail.flags || [];

                  return (
                    <tr key={project.id} className="transition hover:bg-white/[0.04]">
                      <td className="p-4 font-mono text-slate-500">{(page - 1) * PAGE_SIZE + index + 1}</td>
                      <td className="max-w-[300px] p-4 font-bold text-white">
                        <Link to={`/projects/${project.id}`} className="line-clamp-2 hover:text-cyan-300">{project.title}</Link>
                      </td>
                      <td className="p-4">{project.mp_name || 'N/A'}</td>
                      <td className="p-4">{project.state || 'N/A'}</td>
                      <td className="p-4">{getWorkType(project)}</td>
                      <td className="p-4 font-mono text-slate-200">₹{amountLakhs(project).toFixed(2)}</td>
                      <td className="p-4">
                        <div className="flex min-w-36 items-center gap-3">
                          <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-800">
                            <div className={`h-full rounded-full ${riskTone(score)}`} style={{ width: `${score}%` }} />
                          </div>
                          <span className="w-8 font-mono text-slate-100">{score.toFixed(0)}</span>
                        </div>
                      </td>
                      <td className="p-4"><RiskBadge level={project.risk_level} /></td>
                      <td className="max-w-[260px] p-4">
                        {flags.length === 0 ? (
                          <span className="text-slate-500">None</span>
                        ) : (
                          <div className="flex flex-wrap gap-1.5">
                            {flags.slice(0, 3).map((flag) => (
                              <span key={flag.id || flag.flag_type} className="rounded-full border border-white/10 bg-slate-900 px-2 py-1 text-[11px] font-semibold text-slate-200">
                                {flagIcon(flag.severity)} {flag.flag_type}
                              </span>
                            ))}
                            {flags.length > 3 ? <span className="rounded-full bg-slate-800 px-2 py-1 text-[11px] text-slate-400">+{flags.length - 3}</span> : null}
                          </div>
                        )}
                      </td>
                      <td className="p-4 text-right">
                        <Link to={`/projects/${project.id}`} className="inline-flex h-9 items-center rounded-lg border border-cyan-400/25 bg-cyan-400/10 px-3 text-xs font-bold text-cyan-100 transition hover:bg-cyan-400/20">
                          View Details
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-800 p-4 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <span>Page {page} of {totalPages} | 20 per page</span>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page === 1} className="rounded-lg border border-slate-700 px-3 py-2 font-bold text-slate-200 disabled:opacity-40">Previous</button>
            <button type="button" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page === totalPages} className="rounded-lg border border-slate-700 px-3 py-2 font-bold text-slate-200 disabled:opacity-40">Next</button>
          </div>
        </div>
      </div>
    </div>
  );
}
