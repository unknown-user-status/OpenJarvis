/**
 * LeaderboardPage — Community savings leaderboard
 *
 * Fetches entries from Supabase (public anon read) and shows:
 * - Community summary stats
 * - Top 50 ranked users by $ saved
 * - Your own stats (from local savings polling)
 * - Opt-in / join leaderboard section
 */

import { useState, useEffect } from 'react';
import {
  Trophy, DollarSign, Zap, Hash, MessageSquare, TrendingUp,
  Users, Award, ExternalLink, Loader2, RefreshCw,
} from 'lucide-react';
import { useAppStore } from '../lib/store';

// ---------------------------------------------------------------------------
// Supabase config (same as api.ts)
// ---------------------------------------------------------------------------

const SUPABASE_URL = 'https://mtbtgpwzrbostweaanpr.supabase.co';
const SUPABASE_ANON_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im10YnRncHd6cmJvc3R3ZWFhbnByIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxODk0OTQsImV4cCI6MjA4ODc2NTQ5NH0._xMlqCfljtXpwPj54H-ghxfLFO-jiq4W2WhpU8vVL1c';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LeaderboardEntry {
  display_name: string;
  dollar_savings: number;
  energy_wh_saved: number;
  flops_saved: number;
  total_calls: number;
  total_tokens: number;
}

interface CommunityStats {
  memberCount: number;
  totalDollarsSaved: number;
  totalRequests: number;
  totalTokens: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt$(n: number): string {
  return n < 0.01 ? '<$0.01' : `$${n.toFixed(2)}`;
}

function fmtFlops(n: number): string {
  if (n >= 1e15) return `${(n / 1e15).toFixed(1)} P`;
  if (n >= 1e12) return `${(n / 1e12).toFixed(1)} T`;
  if (n >= 1e9)  return `${(n / 1e9).toFixed(1)} G`;
  return n.toLocaleString();
}

function fmtWh(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(2)} kWh`;
  return `${n.toFixed(2)} Wh`;
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: typeof Trophy;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div
      className="flex flex-col gap-1 p-4 rounded-xl"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex items-center gap-2">
        <Icon size={14} style={{ color }} />
        <span className="text-xs uppercase tracking-widest font-semibold" style={{ color: 'var(--color-text-tertiary)' }}>
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold mt-1" style={{ color: 'var(--color-text)' }}>
        {value}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [stats, setStats] = useState<CommunityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const savings = useAppStore((s) => s.savings);
  const optInEnabled = useAppStore((s) => s.optInEnabled);
  const optInDisplayName = useAppStore((s) => s.optInDisplayName);
  const setOptInModalOpen = useAppStore((s) => s.setOptInModalOpen);

  const fetchLeaderboard = async () => {
    setLoading(true);
    setError('');
    try {
      const headers = {
        apikey: SUPABASE_ANON_KEY,
        Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
      };

      const res = await fetch(
        `${SUPABASE_URL}/rest/v1/savings_entries?select=display_name,dollar_savings,energy_wh_saved,flops_saved,total_calls,total_tokens&order=dollar_savings.desc&limit=50`,
        { headers },
      );

      if (!res.ok) throw new Error(`Supabase error: ${res.status}`);
      const data: LeaderboardEntry[] = await res.json();
      setEntries(data);

      const communityStats: CommunityStats = {
        memberCount: data.length,
        totalDollarsSaved: data.reduce((s, e) => s + (e.dollar_savings ?? 0), 0),
        totalRequests: data.reduce((s, e) => s + (e.total_calls ?? 0), 0),
        totalTokens: data.reduce((s, e) => s + (e.total_tokens ?? 0), 0),
      };
      setStats(communityStats);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load leaderboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLeaderboard(); }, []);

  // Derive local user's savings (Claude Opus 4.6 as baseline)
  const claudeSavings = savings?.per_provider?.find((p) => p.provider === 'claude-opus-4.6');
  const myDollarSavings = claudeSavings?.total_cost ?? 0;
  const myEnergyWh = savings?.per_provider?.reduce((s, p) => s + (p.energy_wh ?? 0), 0) ?? 0;
  const myFlops = savings?.per_provider?.reduce((s, p) => s + (p.flops ?? 0), 0) ?? 0;

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Trophy size={20} style={{ color: 'var(--color-accent-amber, #f59e0b)' }} />
              <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
                Savings Leaderboard
              </h1>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              <button
                onClick={fetchLeaderboard}
                disabled={loading}
                className="p-1.5 rounded-lg transition-colors cursor-pointer"
                style={{ color: 'var(--color-text-secondary)' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                title="Refresh leaderboard"
              >
                <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            See how the OpenJarvis community saves money, energy, and compute by running AI locally
            instead of using cloud providers.
          </p>
        </header>

        {/* Promo banner */}
        <div
          className="flex items-start gap-4 p-4 rounded-xl mb-6"
          style={{
            background: 'var(--color-accent-subtle)',
            border: '1px solid var(--color-accent)',
          }}
        >
          <Award size={20} style={{ color: 'var(--color-accent)', flexShrink: 0, marginTop: 2 }} />
          <div>
            <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>
              Win a Mac Mini! 🎉
            </div>
            <div className="text-sm mt-1" style={{ color: 'var(--color-text-secondary)' }}>
              Opt in to share your savings for a chance to win a Mac Mini. Your data is fully
              anonymous — no email, no IP, no hardware info.
            </div>
          </div>
        </div>

        {/* Community stats */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <StatCard icon={Users} label="Members" value={stats.memberCount.toLocaleString()} color="var(--color-accent)" />
            <StatCard icon={DollarSign} label="Total Saved*" value={fmt$(stats.totalDollarsSaved)} color="var(--color-success, #22c55e)" />
            <StatCard icon={MessageSquare} label="Requests" value={stats.totalRequests.toLocaleString()} color="var(--color-accent-purple, #a78bfa)" />
            <StatCard icon={Hash} label="Tokens" value={stats.totalTokens >= 1e9 ? `${(stats.totalTokens / 1e9).toFixed(1)}B` : stats.totalTokens.toLocaleString()} color="var(--color-accent-amber, #f59e0b)" />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          {/* Leaderboard table */}
          <div className="lg:col-span-2">
            <div
              className="rounded-xl overflow-hidden"
              style={{ border: '1px solid var(--color-border)' }}
            >
              <div
                className="px-4 py-3 flex items-center gap-2"
                style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface)' }}
              >
                <TrendingUp size={13} style={{ color: 'var(--color-accent)' }} />
                <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--color-text-tertiary)' }}>
                  Top Contributors
                </span>
              </div>

              {loading ? (
                <div className="flex items-center justify-center gap-2 py-12" style={{ color: 'var(--color-text-tertiary)' }}>
                  <Loader2 size={16} className="animate-spin" />
                  <span className="text-sm">Loading leaderboard…</span>
                </div>
              ) : error ? (
                <div className="py-12 text-center text-sm" style={{ color: 'var(--color-error, #ef4444)' }}>
                  {error}
                </div>
              ) : entries.length === 0 ? (
                <div className="py-12 text-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
                  No entries yet — be the first to join!
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}>
                        {['#', 'Name', '$ Saved*', 'Energy', 'FLOPs', 'Req', 'Tokens'].map((h) => (
                          <th key={h} className="px-3 py-2 text-left font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-tertiary)' }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {entries.map((entry, i) => {
                        const isMe = optInEnabled && entry.display_name === optInDisplayName;
                        return (
                          <tr
                            key={i}
                            style={{
                              borderBottom: '1px solid var(--color-border)',
                              background: isMe ? 'var(--color-accent-subtle)' : i % 2 === 0 ? 'var(--color-surface)' : 'transparent',
                            }}
                          >
                            <td className="px-3 py-2 font-mono" style={{ color: i < 3 ? 'var(--color-accent-amber, #f59e0b)' : 'var(--color-text-tertiary)' }}>
                              {i < 3 ? ['🥇', '🥈', '🥉'][i] : i + 1}
                            </td>
                            <td className="px-3 py-2 font-medium" style={{ color: isMe ? 'var(--color-accent)' : 'var(--color-text)' }}>
                              {entry.display_name || 'Anonymous'}
                              {isMe && <span className="ml-1 text-[10px] opacity-70">(you)</span>}
                            </td>
                            <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-success, #22c55e)' }}>
                              {fmt$(entry.dollar_savings ?? 0)}
                            </td>
                            <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                              {fmtWh(entry.energy_wh_saved ?? 0)}
                            </td>
                            <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                              {fmtFlops(entry.flops_saved ?? 0)}
                            </td>
                            <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                              {(entry.total_calls ?? 0).toLocaleString()}
                            </td>
                            <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                              {(entry.total_tokens ?? 0).toLocaleString()}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Right column: Your stats + opt-in */}
          <div className="flex flex-col gap-3">
            {/* Your stats card */}
            <div
              className="rounded-xl p-4"
              style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Zap size={13} style={{ color: 'var(--color-accent)' }} />
                <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--color-text-tertiary)' }}>
                  Your Stats (This Session)
                </span>
              </div>
              {savings && savings.total_tokens > 0 ? (
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--color-text-secondary)' }}>$ Saved*</span>
                    <span className="font-mono font-semibold" style={{ color: 'var(--color-success, #22c55e)' }}>
                      {fmt$(myDollarSavings)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--color-text-secondary)' }}>Energy saved</span>
                    <span className="font-mono" style={{ color: 'var(--color-text)' }}>
                      {fmtWh(myEnergyWh)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--color-text-secondary)' }}>FLOPs</span>
                    <span className="font-mono" style={{ color: 'var(--color-text)' }}>
                      {fmtFlops(myFlops)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--color-text-secondary)' }}>Requests</span>
                    <span className="font-mono" style={{ color: 'var(--color-text)' }}>
                      {savings.total_calls.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--color-text-secondary)' }}>Tokens</span>
                    <span className="font-mono" style={{ color: 'var(--color-text)' }}>
                      {savings.total_tokens.toLocaleString()}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  No inference runs yet this session. Ask Jarvis something first!
                </p>
              )}
            </div>

            {/* Opt-in card */}
            <div
              className="rounded-xl p-4"
              style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Trophy size={13} style={{ color: 'var(--color-accent-amber, #f59e0b)' }} />
                <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--color-text-tertiary)' }}>
                  Leaderboard
                </span>
              </div>
              {optInEnabled ? (
                <div>
                  <div
                    className="flex items-center gap-2 px-3 py-2 rounded-lg mb-3"
                    style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)' }}
                  >
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', display: 'inline-block', flexShrink: 0 }} />
                    <span className="text-xs font-medium" style={{ color: '#22c55e' }}>
                      You're on the leaderboard
                      {optInDisplayName && ` as "${optInDisplayName}"`}!
                    </span>
                  </div>
                  <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    Your stats are submitted automatically every 30 seconds.
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-xs mb-3" style={{ color: 'var(--color-text-secondary)' }}>
                    Share your anonymous savings to appear on the leaderboard and enter the Mac Mini giveaway.
                  </p>
                  <button
                    onClick={() => setOptInModalOpen(true)}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer"
                    style={{
                      background: 'var(--color-accent)',
                      color: '#fff',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                  >
                    <Trophy size={14} />
                    Join Leaderboard
                  </button>
                </div>
              )}
            </div>

            {/* External link */}
            <a
              href="https://open-jarvis.github.io/OpenJarvis/leaderboard/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs transition-colors"
              style={{
                background: 'var(--color-bg-secondary)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-secondary)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
            >
              <ExternalLink size={12} />
              View on OpenJarvis Docs
            </a>
          </div>
        </div>

        {/* Footnote */}
        <p className="text-[11px] mt-2" style={{ color: 'var(--color-text-tertiary)' }}>
          *Dollar savings estimated vs. Claude Opus 4.6 API pricing ($5/1M input, $25/1M output tokens).
          Assumes local open-source models produce roughly the same number of tokens per request as cloud models.
        </p>
      </div>
    </div>
  );
}
