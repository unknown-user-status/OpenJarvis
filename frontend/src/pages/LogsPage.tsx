import { useState, useRef, useEffect } from 'react';
import { Copy, Trash2, Wifi, WifiOff, Server } from 'lucide-react';
import { useAppStore } from '../lib/store';
import { subscribeBackendLogs, type BackendLogEntry } from '../lib/api';

const LEVEL_COLORS: Record<string, string> = {
  debug: 'var(--color-text-tertiary)',
  info: 'var(--color-text)',
  warning: 'var(--color-warning)',
  warn: 'var(--color-warning)',
  error: 'var(--color-error)',
  critical: 'var(--color-error)',
};

const LEVEL_ORDER = ['debug', 'info', 'warning', 'warn', 'error', 'critical'];

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

type LogSource = 'frontend' | 'backend';

interface UnifiedLogEntry {
  id: string;
  ts: number;
  level: string;
  category: string;
  message: string;
  source: LogSource;
}

export function LogsPage() {
  const logEntries = useAppStore((s) => s.logEntries);
  const clearLogs = useAppStore((s) => s.clearLogs);
  const bottomRef = useRef<HTMLDivElement>(null);

  const [backendLogs, setBackendLogs] = useState<UnifiedLogEntry[]>([]);
  const [backendConnected, setBackendConnected] = useState(false);
  const [tab, setTab] = useState<'all' | 'frontend' | 'backend'>('all');
  const [levelFilter, setLevelFilter] = useState<string>('debug');

  // Subscribe to backend SSE log stream
  useEffect(() => {
    const unsub = subscribeBackendLogs(
      (entry: BackendLogEntry) => {
        setBackendConnected(true);
        setBackendLogs((prev) => {
          const next = [
            ...prev,
            {
              id: `be-${entry.ts}-${Math.random().toString(36).slice(2)}`,
              ts: entry.ts,
              level: entry.level,
              category: entry.name,
              message: entry.message,
              source: 'backend' as LogSource,
            },
          ];
          // Cap at 2000 entries
          return next.length > 2000 ? next.slice(next.length - 2000) : next;
        });
      },
      () => setBackendConnected(false),
    );
    return unsub;
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logEntries.length, backendLogs.length]);

  // Merge and sort all log entries
  const frontendMapped: UnifiedLogEntry[] = logEntries.map((e, i) => ({
    id: `fe-${e.timestamp}-${i}`,
    ts: e.timestamp,
    level: e.level,
    category: e.category,
    message: e.message,
    source: 'frontend' as LogSource,
  }));

  const levelIdx = (l: string) => {
    const n = l === 'warn' ? 'warning' : l;
    const idx = LEVEL_ORDER.indexOf(n);
    return idx === -1 ? 0 : idx;
  };
  const filterIdx = levelIdx(levelFilter);

  const allEntries = [...frontendMapped, ...backendLogs]
    .filter((e) => {
      if (tab === 'frontend' && e.source !== 'frontend') return false;
      if (tab === 'backend' && e.source !== 'backend') return false;
      return levelIdx(e.level) >= filterIdx;
    })
    .sort((a, b) => a.ts - b.ts);

  const handleCopy = async () => {
    const text = allEntries
      .map((e) => `${formatTime(e.ts)} [${e.level}] [${e.category}] ${e.message}`)
      .join('\n');
    await navigator.clipboard.writeText(text);
  };

  const handleClear = () => {
    clearLogs();
    setBackendLogs([]);
  };

  const tabStyle = (t: typeof tab) => ({
    padding: '4px 12px',
    borderRadius: 8,
    fontSize: 12,
    cursor: 'pointer',
    background: tab === t ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
    color: tab === t ? 'white' : 'var(--color-text-secondary)',
    border: tab === t ? '1px solid var(--color-accent)' : '1px solid var(--color-border)',
  } as React.CSSProperties);

  return (
    <div className="flex-1 flex flex-col overflow-hidden px-6 py-10">
      <div className="max-w-5xl mx-auto w-full flex flex-col flex-1 overflow-hidden">
        <header className="mb-4 shrink-0">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
              Logs
            </h1>
            <div className="flex items-center gap-2 flex-wrap">
              {/* Backend connection indicator */}
              <div className="flex items-center gap-1.5 text-xs" style={{ color: backendConnected ? 'var(--color-success)' : 'var(--color-text-tertiary)' }}>
                {backendConnected
                  ? <Wifi size={12} />
                  : <WifiOff size={12} />}
                {backendConnected ? 'server live' : 'server offline'}
              </div>
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {allEntries.length} entries
              </span>
              {/* Level filter */}
              <select
                value={levelFilter}
                onChange={(e) => setLevelFilter(e.target.value)}
                className="text-xs rounded-lg px-2 py-1 outline-none cursor-pointer"
                style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
              >
                <option value="debug">All levels</option>
                <option value="info">Info+</option>
                <option value="warning">Warn+</option>
                <option value="error">Errors only</option>
              </select>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
              >
                <Copy size={12} /> Copy All
              </button>
              <button
                onClick={handleClear}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
              >
                <Trash2 size={12} /> Clear
              </button>
            </div>
          </div>

          <p className="text-sm mt-2" style={{ color: 'var(--color-text-secondary)' }}>
            Real-time log stream from the UI and the backend server.
          </p>

          {/* Source tabs */}
          <div className="flex items-center gap-2 mt-3">
            <button style={tabStyle('all')} onClick={() => setTab('all')}>All</button>
            <button style={tabStyle('frontend')} onClick={() => setTab('frontend')}>Frontend</button>
            <button style={tabStyle('backend')} onClick={() => setTab('backend')}>
              <Server size={10} className="inline mr-1" />
              Backend
            </button>
          </div>
        </header>

        {/* Log entries */}
        <div
          className="flex-1 overflow-y-auto rounded-xl p-4 font-mono text-xs leading-relaxed"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          {allEntries.length === 0 ? (
            <div className="text-center py-12" style={{ color: 'var(--color-text-tertiary)' }}>
              {tab === 'backend' && !backendConnected
                ? 'Backend server not reachable — start the server to stream logs here.'
                : 'No log entries yet. Interact with the app or use a model to see logs.'}
            </div>
          ) : (
            allEntries.map((entry) => (
              <div key={entry.id} className="py-0.5 flex items-start gap-1">
                <span style={{ color: 'var(--color-text-tertiary)', flexShrink: 0 }}>{formatTime(entry.ts)}</span>
                {' '}
                <span
                  className="px-1 rounded"
                  style={{
                    fontSize: 10,
                    background: entry.source === 'backend'
                      ? 'color-mix(in srgb, var(--color-accent) 15%, transparent)'
                      : 'color-mix(in srgb, var(--color-accent-purple) 15%, transparent)',
                    color: entry.source === 'backend' ? 'var(--color-accent)' : 'var(--color-accent-purple)',
                    flexShrink: 0,
                  }}
                >
                  {entry.source === 'backend' ? 'srv' : 'ui'}
                </span>
                {' '}
                <span style={{ color: LEVEL_COLORS[entry.level] || 'var(--color-text)', flexShrink: 0 }}>
                  [{entry.category}]
                </span>
                {' '}
                <span style={{ color: LEVEL_COLORS[entry.level] || 'var(--color-text)', wordBreak: 'break-word' }}>
                  {entry.message}
                </span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
