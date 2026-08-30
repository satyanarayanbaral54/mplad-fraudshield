import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function Navbar() {
  const location = useLocation();
  const navItems = [
    { label: 'Dashboard', path: '/' },
    { label: 'Projects', path: '/projects' },
    { label: 'Vendor Network', path: '/vendors' },
    { label: 'Geo Map', path: '/map' },
    { label: 'Surveys', path: '/surveys' },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-slate-700/70 bg-slate-800/95 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-emerald-400/30 bg-emerald-500/15 text-lg font-black text-emerald-300">
            FS
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-base font-bold text-white sm:text-lg">MPLAD FraudShield</span>
              <span className="flag-chip border-blue-400/30 bg-blue-500/15 text-blue-200">SIH 2025</span>
            </div>
            <p className="hidden text-xs text-slate-400 sm:block">Forensic audit command center</p>
          </div>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => {
            const active = item.path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`border-b-2 px-3 py-5 text-sm font-semibold transition ${
                  active
                    ? 'border-emerald-400 text-white'
                    : 'border-transparent text-slate-300 hover:border-slate-500 hover:text-white'
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden text-sm font-semibold text-slate-200 sm:inline">India 🇮🇳</span>
          <span className="flag-chip border-emerald-400/30 bg-emerald-500/15 text-emerald-200">Auditor Mode</span>
        </div>
      </div>
    </header>
  );
}
