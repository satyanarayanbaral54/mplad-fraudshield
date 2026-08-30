import React from 'react';

export default function RiskBadge({ level }) {
  const styles = {
    LOW: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    MEDIUM: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    HIGH: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    CRITICAL: 'bg-rose-500/10 text-rose-400 border-rose-500/30 animate-pulse',
  };

  const currentStyle = styles[level] || 'bg-slate-800 text-slate-400 border-slate-700';

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${currentStyle}`}>
      <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
        level === 'CRITICAL' ? 'bg-rose-400' :
        level === 'HIGH' ? 'bg-orange-400' :
        level === 'MEDIUM' ? 'bg-amber-400' : 'bg-emerald-400'
      }`} />
      {level || 'UNKNOWN'}
    </span>
  );
}
