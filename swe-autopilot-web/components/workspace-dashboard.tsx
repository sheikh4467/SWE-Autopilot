"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";

type AuthUser = {
  id: number;
  email: string;
  name: string;
  created_at: string;
};

type Metric = {
  key: string;
  label: string;
  value: number;
  tone: string;
};

type DistributionItem = {
  label: string;
  value: number;
  tone: string;
};

type Stats = {
  metrics: Metric[];
  distribution: DistributionItem[];
  activity: { label: string; value: number }[];
  last_updated: string;
  note: string;
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const toneClass: Record<string, string> = {
  cyan: "chart-cyan",
  violet: "chart-violet",
  lime: "chart-lime",
  orange: "chart-orange",
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function LineChart({ activity }: { activity: Stats["activity"] }) {
  const max = Math.max(1, ...activity.map((point) => point.value));
  const points = activity.map((point, index) => {
    const x = activity.length === 1 ? 50 : (index / (activity.length - 1)) * 100;
    const y = 88 - (point.value / max) * 68;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div className="line-chart-wrap">
      <svg className="line-chart" viewBox="0 0 100 100" role="img" aria-label="Workspace activity over the last seven days">
        <defs>
          <linearGradient id="activity-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#65e9ff" stopOpacity="0.32" />
            <stop offset="1" stopColor="#65e9ff" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[20, 42, 64, 86].map((y) => <line key={y} x1="0" x2="100" y1={y} y2={y} className="chart-grid-line" />)}
        <polygon points={`0,100 ${points} 100,100`} fill="url(#activity-fill)" />
        <polyline points={points} fill="none" className="activity-line" />
        {activity.map((point, index) => {
          const x = activity.length === 1 ? 50 : (index / (activity.length - 1)) * 100;
          const y = 88 - (point.value / max) * 68;
          return <circle key={`${point.label}-${index}`} cx={x} cy={y} r="1.7" className="activity-dot" />;
        })}
      </svg>
      <div className="chart-axis-labels">
        {activity.map((point) => <span key={point.label}>{point.label}</span>)}
      </div>
    </div>
  );
}

function BarChart({ metrics }: { metrics: Metric[] }) {
  const max = Math.max(1, ...metrics.map((metric) => metric.value));
  return (
    <div className="bar-chart" role="img" aria-label="Workspace work counters">
      {metrics.map((metric) => (
        <div className="bar-chart-item" key={metric.key}>
          <div className="bar-chart-track"><span className={toneClass[metric.tone] ?? "chart-cyan"} style={{ height: `${Math.max(metric.value === 0 ? 4 : 12, (metric.value / max) * 100)}%` }} /></div>
          <strong>{metric.value}</strong>
          <small>{metric.label}</small>
        </div>
      ))}
    </div>
  );
}

function DonutChart({ distribution }: { distribution: Stats["distribution"] }) {
  const total = distribution.reduce((sum, item) => sum + item.value, 0);
  const circumference = 2 * Math.PI * 34;
  let offset = 0;

  return (
    <div className="donut-layout">
      <div className="donut-chart-wrap">
        <svg className="donut-chart" viewBox="0 0 100 100" role="img" aria-label="Workspace work distribution">
          <circle cx="50" cy="50" r="34" className="donut-track" />
          {total > 0 ? distribution.map((item) => {
            const length = (item.value / total) * circumference;
            const circle = (
              <circle
                key={item.label}
                cx="50"
                cy="50"
                r="34"
                className={`donut-segment ${toneClass[item.tone] ?? "chart-cyan"}`}
                strokeDasharray={`${length} ${circumference - length}`}
                strokeDashoffset={-offset}
              />
            );
            offset += length;
            return circle;
          }) : <circle cx="50" cy="50" r="34" className="donut-segment chart-muted" strokeDasharray={`8 ${circumference - 8}`} />}
        </svg>
        <div className="donut-center"><strong>{total}</strong><span>items</span></div>
      </div>
      <div className="donut-legend">
        {distribution.map((item) => <div key={item.label}><span className={`legend-dot ${toneClass[item.tone] ?? "chart-cyan"}`} /><span>{item.label}</span><strong>{item.value}</strong></div>)}
      </div>
    </div>
  );
}

export function WorkspaceDashboard() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState("");

  const loadDashboard = async () => {
    try {
      const meResponse = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
      if (!meResponse.ok) {
        window.location.replace("/?openAuth=login");
        return;
      }
      const currentUser = (await meResponse.json()) as AuthUser;
      const statsResponse = await fetch(`${API_URL}/workspace/stats`, { credentials: "include" });
      if (!statsResponse.ok) throw new Error("Unable to load workspace telemetry.");
      const currentStats = (await statsResponse.json()) as Stats;
      setUser(currentUser);
      setStats(currentStats);
      setLastRefresh(new Date().toISOString());
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load your workspace.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    window.history.replaceState({}, document.title, window.location.pathname);
    void loadDashboard();
    const interval = window.setInterval(() => void loadDashboard(), 10000);
    return () => window.clearInterval(interval);
  }, []);

  const totalWorkItems = useMemo(
    () => stats?.distribution.reduce((sum, item) => sum + item.value, 0) ?? 0,
    [stats],
  );

  const logout = async () => {
    await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" }).catch(() => undefined);
    window.location.replace("/");
  };

  return (
    <main className="workspace-shell">
      <div className="ambient ambient-one" aria-hidden="true" />
      <div className="ambient ambient-two" aria-hidden="true" />
      <div className="page-grid" aria-hidden="true" />
      <div className="noise-layer" aria-hidden="true" />
      <header className="workspace-header">
        <Link href="/" aria-label="SWE Autopilot home"><BrandMark /></Link>
        <nav className="workspace-nav" aria-label="Workspace navigation">
          <Link className="is-active" href="/workspace">Overview</Link>
          <Link href="/platform">Platform</Link>
          <Link href="/workflow">Workflow</Link>
          <Link href="/security">Security</Link>
        </nav>
        <div className="workspace-user">
          <span>{user ? user.name : "Loading profile"}</span>
          <button onClick={logout}>Sign out</button>
        </div>
      </header>

      <section className="workspace-hero">
        <div>
          <span className="section-kicker">Live workspace / telemetry</span>
          <h1>Welcome back{user ? `, ${user.name}` : ""}.</h1>
          <p>Here is the current pulse of your software engineering workspace. Data refreshes automatically every 10 seconds.</p>
        </div>
        <div className="workspace-status-orb" aria-hidden="true"><span /><strong>LIVE</strong><small>runtime link</small></div>
      </section>

      {loading && <div className="workspace-loading">Loading your workspace telemetry…</div>}
      {error && <div className="workspace-error" role="alert">{error}</div>}

      {stats && (
        <>
          <section className="workspace-metrics">
            {stats.metrics.map((metric) => <article className="workspace-metric" key={metric.key}><span className={`metric-glow ${toneClass[metric.tone] ?? "chart-cyan"}`} /><small>{metric.label}</small><strong>{metric.value}</strong><span className="metric-caption">live count</span></article>)}
          </section>

          <section className="workspace-chart-grid">
            <article className="workspace-panel workspace-panel-wide">
              <div className="workspace-panel-heading"><div><span className="section-kicker">Activity stream</span><h2>Workspace motion</h2></div><span className="live-badge"><i /> auto refresh</span></div>
              <LineChart activity={stats.activity} />
            </article>
            <article className="workspace-panel">
              <div className="workspace-panel-heading"><div><span className="section-kicker">Distribution</span><h2>Work mix</h2></div></div>
              <DonutChart distribution={stats.distribution} />
            </article>
            <article className="workspace-panel">
              <div className="workspace-panel-heading"><div><span className="section-kicker">Counters</span><h2>Build pulse</h2></div></div>
              <BarChart metrics={stats.metrics} />
            </article>
            <article className="workspace-panel workspace-panel-wide workspace-panel-note">
              <div className="workspace-panel-heading"><div><span className="section-kicker">Control room note</span><h2>Start with a requirement.</h2></div><span className="workspace-note-number">{totalWorkItems.toString().padStart(2, "0")}</span></div>
              <p>{stats.note}</p>
              <div className="workspace-next-actions"><Link href="/workflow">Review the workflow →</Link><Link href="/platform">Explore the platform →</Link></div>
            </article>
          </section>

          <div className="workspace-footer-meta">Last refreshed {lastRefresh ? formatTime(lastRefresh) : "—"} · telemetry endpoint connected</div>
        </>
      )}
    </main>
  );
}
