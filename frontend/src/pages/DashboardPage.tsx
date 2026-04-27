import { useState, useEffect } from 'react';
import { EnergyDashboard } from '../components/Dashboard/EnergyDashboard';
import { CostComparison } from '../components/Dashboard/CostComparison';
import { SavingsSummaryCard } from '../components/Dashboard/SavingsSummaryCard';
import { TraceDebugger } from '../components/Dashboard/TraceDebugger';
import { checkHealth } from '../lib/api';
import { useAppStore } from '../lib/store';
import { useNavigate } from 'react-router';
import {
  Wifi, WifiOff, RefreshCw, MessageSquare, Bot,
  Database, Settings, CheckCircle2,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Server health banner
// ---------------------------------------------------------------------------
type HealthState = 'checking' | 'online' | 'offline';

function HealthBanner() {
  const [health, setHealth] = useState<HealthState>('checking');
  const [lastChecked, setLastChecked] = useState('');

  const check = async () => {
    setHealth('checking');
    try {
      await checkHealth();
      setHealth('online');
    } catch {
      setHealth('offline');
    }
    setLastChecked(new Date().toLocaleTimeString());
  };

  useEffect(() => {
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, []);

  if (health === 'checking') return null;

  if (health === 'offline') {
    return (
      <div
        className="flex items-start gap-3 p-4 rounded-xl mb-6"
        style={{
          background: 'color-mix(in srgb, var(--color-error) 10%, transparent)',
          border: '1px solid color-mix(in srgb, var(--color-error) 30%, transparent)',
        }}
      >
        <WifiOff size={16} style={{ color: 'var(--color-error)', marginTop: 2, flexShrink: 0 }} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold mb-1" style={{ color: 'var(--color-error)' }}>
            Server offline — dashboard data unavailable
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            Start the server by running <code className="px-1 py-0.5 rounded text-[11px]" style={{ background: 'var(--color-bg-tertiary)' }}>OpenJarvis-GUI.bat</code> (Windows) or <code className="px-1 py-0.5 rounded text-[11px]" style={{ background: 'var(--color-bg-tertiary)' }}>uv run openjarvis server</code>, then reload this page.
          </div>
        </div>
        <button
          onClick={check}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded cursor-pointer"
          style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
        >
          <RefreshCw size={11} /> Retry
        </button>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-2 p-3 rounded-xl mb-6"
      style={{
        background: 'color-mix(in srgb, var(--color-success) 8%, transparent)',
        border: '1px solid color-mix(in srgb, var(--color-success) 25%, transparent)',
      }}
    >
      <Wifi size={14} style={{ color: 'var(--color-success)' }} />
      <span className="text-xs" style={{ color: 'var(--color-success)' }}>Server online</span>
      <span className="text-xs ml-auto" style={{ color: 'var(--color-text-tertiary)' }}>
        checked {lastChecked}
      </span>
      <button
        onClick={check}
        className="flex items-center gap-1 text-xs px-2 py-1 rounded cursor-pointer"
        style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
      >
        <RefreshCw size={10} /> Refresh
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quick-start guide (shown when no data yet)
// ---------------------------------------------------------------------------
function QuickStartGuide() {
  const navigate = useNavigate();

  const steps = [
    {
      icon: MessageSquare,
      title: '1. Start chatting',
      desc: 'Open Chat or Jarvis and send your first message. Every inference populates the telemetry charts.',
      action: () => navigate('/'),
      actionLabel: 'Go to Chat',
      color: 'var(--color-accent)',
    },
    {
      icon: Database,
      title: '2. Connect data sources',
      desc: 'Link Gmail, Google Drive, Notion, Obsidian, Slack, or just paste text so Jarvis can search your knowledge.',
      action: () => navigate('/data-sources'),
      actionLabel: 'Open Data Sources',
      color: 'var(--color-accent-purple)',
    },
    {
      icon: Bot,
      title: '3. Create an agent',
      desc: 'Set up an automated agent that runs on a schedule — daily briefings, research monitors, email summaries.',
      action: () => navigate('/agents'),
      actionLabel: 'Open Agents',
      color: '#f97316',
    },
    {
      icon: Settings,
      title: '4. Configure API keys',
      desc: 'Add keys for cloud models (OpenAI, Claude, Gemini, NVIDIA, Groq…) to unlock cloud inference in agents.',
      action: () => navigate('/settings'),
      actionLabel: 'Open Settings',
      color: '#22d3ee',
    },
  ];

  return (
    <div className="hud-panel p-6 mb-4">
      <h3 className="hud-label flex items-center gap-2 mb-4">
        <CheckCircle2 size={12} style={{ color: 'var(--color-accent)' }} />
        Quick Start
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {steps.map((s) => (
          <div
            key={s.title}
            className="p-4 rounded-xl flex flex-col gap-2"
            style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
          >
            <div className="flex items-center gap-2">
              <s.icon size={14} style={{ color: s.color }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{s.title}</span>
            </div>
            <p className="text-xs flex-1" style={{ color: 'var(--color-text-secondary)' }}>{s.desc}</p>
            <button
              onClick={s.action}
              className="self-start text-xs px-3 py-1 rounded-lg cursor-pointer transition-opacity hover:opacity-80"
              style={{ background: 'var(--color-bg-tertiary)', color: s.color, border: `1px solid ${s.color}` }}
            >
              {s.actionLabel} →
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard info tooltips
// ---------------------------------------------------------------------------
function DashboardInfoBar() {
  return (
    <div
      className="flex flex-wrap items-center gap-4 px-4 py-3 rounded-xl mb-4 text-xs"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-tertiary)' }}
    >
      <span className="flex items-center gap-1.5">
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-success)', display: 'inline-block' }} />
        <strong style={{ color: 'var(--color-text-secondary)' }}>Energy</strong> — live watts measured from your GPU/CPU during inference
      </span>
      <span className="flex items-center gap-1.5">
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-accent)', display: 'inline-block' }} />
        <strong style={{ color: 'var(--color-text-secondary)' }}>Cost Comparison</strong> — local cost vs equivalent cloud API spend
      </span>
      <span className="flex items-center gap-1.5">
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-accent-purple)', display: 'inline-block' }} />
        <strong style={{ color: 'var(--color-text-secondary)' }}>Traces</strong> — step-by-step debug log of each inference
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const now = new Date();
  const stamp = now.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  const savings = useAppStore((s) => s.savings);
  const hasData = savings && savings.total_tokens > 0;

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <header className="mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
              System Overview
            </h1>
            <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {stamp}
            </div>
          </div>
          <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
            Live telemetry — power draw, token throughput, and cost savings versus cloud APIs.
          </p>
        </header>

        <HealthBanner />

        {!hasData && <QuickStartGuide />}

        <DashboardInfoBar />

        <div className="mb-4">
          <SavingsSummaryCard />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <EnergyDashboard />
          <CostComparison />
        </div>

        <TraceDebugger />
      </div>
    </div>
  );
}
