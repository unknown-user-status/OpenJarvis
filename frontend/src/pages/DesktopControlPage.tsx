import { useState, useRef, useEffect, useCallback } from 'react';
import { Monitor, Play, Square, Loader2, Zap, Terminal, CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import { runDesktopGoal, takeScreenshot } from '../lib/api';

interface ActionLogEntry {
  id: string;
  step: number;
  action: string;
  result: string;
  success: boolean;
  ts: number;
}

type RunState = 'idle' | 'running' | 'done' | 'error';

const EXAMPLE_GOALS = [
  'Open Chrome and go to google.com',
  'Open Notepad and type "Hello from Jarvis"',
  'Take a screenshot and save it to the Desktop',
  'Search for the weather in Chrome',
  'Close all open Notepad windows',
  'Open File Explorer',
  'Set volume to 50%',
];

export function DesktopControlPage() {
  const [goal, setGoal] = useState('');
  const [runState, setRunState] = useState<RunState>('idle');
  const [log, setLog] = useState<ActionLogEntry[]>([]);
  const [summary, setSummary] = useState('');
  const [error, setError] = useState('');
  const [screenshot, setScreenshot] = useState<string>('');
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef(false);

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [log]);

  const refreshScreenshot = useCallback(async () => {
    setScreenshotLoading(true);
    try {
      const b64 = await takeScreenshot();
      setScreenshot(b64);
    } catch {
      // silently ignore
    } finally {
      setScreenshotLoading(false);
    }
  }, []);

  // Refresh screenshot every 3s while running
  useEffect(() => {
    if (runState !== 'running') return;
    const id = setInterval(refreshScreenshot, 3000);
    return () => clearInterval(id);
  }, [runState, refreshScreenshot]);

  const handleRun = async () => {
    if (!goal.trim() || runState === 'running') return;
    abortRef.current = false;
    setRunState('running');
    setLog([]);
    setSummary('');
    setError('');
    await refreshScreenshot();

    try {
      const result = await runDesktopGoal(goal.trim(), (entry) => {
        setLog((prev) => [...prev, {
          id: Date.now().toString(36) + Math.random().toString(36).slice(2),
          step: entry.step,
          action: entry.action,
          result: entry.result,
          success: entry.success,
          ts: Date.now(),
        }]);
      });
      setSummary(result.summary || 'Task complete.');
      setRunState('done');
      await refreshScreenshot();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setRunState('error');
    }
  };

  const handleStop = () => {
    abortRef.current = true;
    setRunState('idle');
  };

  const isRunning = runState === 'running';

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: Controls + Log */}
      <div className="flex flex-col w-[360px] shrink-0 overflow-hidden" style={{ borderRight: '1px solid var(--color-border)' }}>
        {/* Header */}
        <div className="px-4 py-4 shrink-0" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <Monitor size={16} style={{ color: 'var(--color-accent)' }} />
            <h1 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>Desktop Control</h1>
          </div>
          <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            Tell Jarvis what to do on your machine
          </p>
        </div>

        {/* Goal input */}
        <div className="px-4 py-3 shrink-0" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleRun(); }}
            placeholder="What should Jarvis do? (Ctrl+Enter to run)"
            rows={3}
            disabled={isRunning}
            className="w-full text-sm rounded-lg px-3 py-2 resize-none outline-none"
            style={{
              background: 'var(--color-input-bg)',
              border: '1px solid var(--color-input-border)',
              color: 'var(--color-text)',
            }}
          />
          <div className="flex gap-2 mt-2">
            {isRunning ? (
              <button
                onClick={handleStop}
                className="flex-1 flex items-center justify-center gap-2 text-sm py-2 rounded-lg transition-colors cursor-pointer"
                style={{ background: 'var(--color-error)', color: 'white' }}
              >
                <Square size={14} />
                Stop
              </button>
            ) : (
              <button
                onClick={handleRun}
                disabled={!goal.trim()}
                className="flex-1 flex items-center justify-center gap-2 text-sm py-2 rounded-lg transition-colors cursor-pointer"
                style={{
                  background: goal.trim() ? 'var(--color-accent)' : 'var(--color-disabled-bg)',
                  color: goal.trim() ? 'white' : 'var(--color-text-tertiary)',
                  cursor: goal.trim() ? 'pointer' : 'default',
                }}
              >
                {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                {isRunning ? 'Running…' : 'Run'}
              </button>
            )}
          </div>

          {/* Example goals */}
          <div className="mt-3">
            <p className="text-[10px] uppercase tracking-wide mb-1.5 font-medium" style={{ color: 'var(--color-text-tertiary)' }}>
              Examples
            </p>
            <div className="flex flex-col gap-1">
              {EXAMPLE_GOALS.map((eg) => (
                <button
                  key={eg}
                  onClick={() => setGoal(eg)}
                  disabled={isRunning}
                  className="text-left text-xs px-2 py-1 rounded transition-colors truncate cursor-pointer"
                  style={{ color: 'var(--color-text-secondary)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <Zap size={9} className="inline mr-1" style={{ color: 'var(--color-accent-amber)' }} />
                  {eg}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Action log */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <Terminal size={12} style={{ color: 'var(--color-text-tertiary)' }} />
            <span className="text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Action Log
            </span>
            {isRunning && <Loader2 size={10} className="animate-spin ml-auto" style={{ color: 'var(--color-accent)' }} />}
          </div>

          {log.length === 0 && runState === 'idle' && (
            <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              Actions will appear here as Jarvis works…
            </p>
          )}

          <div className="flex flex-col gap-1.5">
            {log.map((entry) => (
              <div
                key={entry.id}
                className="rounded-lg px-3 py-2 text-xs"
                style={{
                  background: entry.success ? 'var(--color-bg-secondary)' : 'color-mix(in srgb, var(--color-error) 8%, transparent)',
                  border: `1px solid ${entry.success ? 'var(--color-border)' : 'color-mix(in srgb, var(--color-error) 20%, transparent)'}`,
                }}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  {entry.success
                    ? <CheckCircle size={10} style={{ color: 'var(--color-success)' }} />
                    : <XCircle size={10} style={{ color: 'var(--color-error)' }} />}
                  <span className="font-mono font-medium" style={{ color: 'var(--color-text)' }}>
                    Step {entry.step}: {entry.action}
                  </span>
                </div>
                <p className="line-clamp-2 pl-4" style={{ color: 'var(--color-text-secondary)' }}>
                  {entry.result}
                </p>
              </div>
            ))}
          </div>

          {/* Summary / error */}
          {runState === 'done' && summary && (
            <div
              className="mt-3 rounded-lg px-3 py-2 text-xs"
              style={{ background: 'color-mix(in srgb, var(--color-success) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-success) 20%, transparent)' }}
            >
              <div className="flex items-center gap-1.5 mb-0.5">
                <CheckCircle size={10} style={{ color: 'var(--color-success)' }} />
                <span className="font-medium" style={{ color: 'var(--color-success)' }}>Done</span>
              </div>
              <p style={{ color: 'var(--color-text)' }}>{summary}</p>
            </div>
          )}

          {runState === 'error' && error && (
            <div
              className="mt-3 rounded-lg px-3 py-2 text-xs"
              style={{ background: 'color-mix(in srgb, var(--color-error) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-error) 20%, transparent)' }}
            >
              <div className="flex items-center gap-1.5 mb-0.5">
                <XCircle size={10} style={{ color: 'var(--color-error)' }} />
                <span className="font-medium" style={{ color: 'var(--color-error)' }}>Error</span>
              </div>
              <p style={{ color: 'var(--color-text)' }}>{error}</p>
            </div>
          )}

          <div ref={logEndRef} />
        </div>
      </div>

      {/* Right: Live screenshot */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div
          className="flex items-center justify-between px-4 py-3 shrink-0"
          style={{ borderBottom: '1px solid var(--color-border)' }}
        >
          <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>Live Screen</span>
          <button
            onClick={refreshScreenshot}
            disabled={screenshotLoading}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
            style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
          >
            <RefreshCw size={12} className={screenshotLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        <div className="flex-1 overflow-auto flex items-center justify-center p-4" style={{ background: 'var(--color-bg)' }}>
          {screenshot ? (
            <img
              src={`data:image/png;base64,${screenshot}`}
              alt="Current screen"
              className="max-w-full max-h-full rounded-lg shadow-lg object-contain"
              style={{ border: '1px solid var(--color-border)' }}
            />
          ) : (
            <div className="flex flex-col items-center gap-3 text-center">
              <Monitor size={40} style={{ color: 'var(--color-text-tertiary)' }} />
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>No screenshot yet</p>
                <p className="text-xs mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
                  Click Refresh or run a goal to see your screen
                </p>
              </div>
              <button
                onClick={refreshScreenshot}
                className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg transition-colors cursor-pointer"
                style={{ background: 'var(--color-accent)', color: 'white' }}
              >
                <RefreshCw size={14} />
                Take Screenshot
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
