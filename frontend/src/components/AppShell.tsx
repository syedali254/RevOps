import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAsync } from '../hooks/useAsync';
import { api } from '../lib/api';
import { Spinner } from './ui';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/campaigns', label: 'Campaigns', end: false },
  { to: '/review', label: 'Review Queue', end: false },
  { to: '/runs', label: 'Workflow runs', end: false },
];

function sectionTitle(pathname: string): string {
  if (pathname === '/') return 'Overview';
  if (pathname.startsWith('/campaigns')) return 'Campaigns';
  if (pathname.startsWith('/review')) return 'Review Queue';
  if (pathname.startsWith('/runs')) return 'Workflow runs';
  return 'B2B Lead Engine';
}

/** Persistent, full-width reminder that this build cannot send anything. */
export function DryRunBanner() {
  return (
    <div
      role="status"
      className="flex h-8 shrink-0 items-center justify-center border-b border-warn/30 bg-warn-bg px-4"
    >
      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-warn">
        Dry run — no messages sent
      </span>
    </div>
  );
}

function ApiStatus() {
  const { data, loading, error } = useAsync(() => api.health(), []);

  if (loading) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-ink-subtle">
        <Spinner />
        Checking backend
      </span>
    );
  }

  if (error) {
    return (
      <span
        title={error}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-danger"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-danger" aria-hidden="true" />
        Backend unreachable
      </span>
    );
  }

  return (
    <span
      title={data?.safety.detail}
      className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-ok" aria-hidden="true" />
      Backend connected · v{data?.version}
    </span>
  );
}

export function AppShell() {
  const location = useLocation();
  const title = sectionTitle(location.pathname);

  return (
    <div className="flex min-h-screen flex-col">
      <DryRunBanner />

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-60 shrink-0 flex-col border-r border-[#1e2330] bg-[#0f1422] text-[#e2e8f0]">
          <div className="flex h-14 items-center gap-3 border-b border-[#1e2330] px-5">
            <span
              aria-hidden="true"
              className="flex h-7 w-7 items-center justify-center rounded bg-accent-500 text-xs font-bold text-white shadow-sm"
            >
              L
            </span>
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-tight text-white">Lead Engine</span>
              <span className="text-[10px] text-accent-100 font-mono">B2B Intelligence</span>
            </div>
          </div>

          <nav className="flex-1 px-3 py-4" aria-label="Primary">
            <ul className="space-y-1">
              {NAV_ITEMS.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `relative flex items-center rounded-md px-3 py-2 text-sm font-medium transition-all ${
                        isActive
                          ? 'bg-accent-600 text-white shadow-xs'
                          : 'text-[#94a3b8] hover:bg-[#1a2030] hover:text-white'
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          <div className="border-t border-[#1e2330] bg-[#0c101c] px-5 py-4">
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-ok animate-pulse" />
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[#94a3b8]">
                Engine Status
              </p>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-[#64748b]">
              Live Tavily, Exa & Groq AI active.
            </p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-line bg-surface px-6">
            <p className="text-sm font-semibold">{title}</p>
            <ApiStatus />
          </header>

          <main className="min-w-0 flex-1 px-6 py-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
