import { TrendingDown, Zap, Cpu, Hash, Trophy } from 'lucide-react';
import { useNavigate } from 'react-router';
import { useAppStore } from '../../lib/store';

const CLOUD_PRICING = [
  { name: 'GPT-5.3', input: 2.00, output: 10.00 },
  { name: 'Claude Opus 4.6', input: 5.00, output: 25.00 },
  { name: 'Gemini 3.1 Pro', input: 2.00, output: 12.00 },
];

// Rough energy & FLOP estimates per token (same as savings.py)
const WH_PER_TOKEN = 0.0003;       // 0.3 Wh per 1k tokens
const GFLOPS_PER_TOKEN = 0.5;      // 0.5 GFLOPs per token for ~7B model

function MetricBadge({ icon: Icon, value, label, color }: {
  icon: typeof TrendingDown;
  value: string;
  label: string;
  color: string;
}) {
  return (
    <div
      className="flex flex-col items-center p-3 rounded-xl gap-1 flex-1 min-w-0"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <Icon size={16} style={{ color }} />
      <div className="text-sm font-semibold font-mono truncate max-w-full" style={{ color: 'var(--color-text)' }}>
        {value}
      </div>
      <div className="text-[10px] text-center" style={{ color: 'var(--color-text-tertiary)' }}>
        {label}
      </div>
    </div>
  );
}

export function SavingsSummaryCard() {
  const savings = useAppStore((s) => s.savings);
  const navigate = useNavigate();

  if (!savings || savings.total_tokens === 0) {
    return (
      <div className="hud-panel p-6">
        <h3 className="hud-label flex items-center gap-2 mb-4">
          <Trophy size={12} style={{ color: 'var(--color-accent)' }} />
          Savings Summary
        </h3>
        <div className="h-28 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
          <span className="hud-mono">no inference data yet — start chatting!</span>
        </div>
      </div>
    );
  }

  const promptK = savings.total_prompt_tokens / 1000;
  const completionK = savings.total_completion_tokens / 1000;

  // Max savings across providers (vs most expensive)
  const maxSaved = Math.max(
    ...CLOUD_PRICING.map((p) => {
      const cloudCost = (promptK * p.input / 1000) + (completionK * p.output / 1000);
      return cloudCost - savings.local_cost;
    }),
  );

  const energyWhSaved = savings.total_tokens * WH_PER_TOKEN;
  const flopsGSaved = savings.total_tokens * GFLOPS_PER_TOKEN;

  const formatFlops = (g: number) => {
    if (g >= 1e9) return `${(g / 1e9).toFixed(1)}Z`;
    if (g >= 1e6) return `${(g / 1e6).toFixed(1)}P`;
    if (g >= 1e3) return `${(g / 1e3).toFixed(1)}T`;
    return `${g.toFixed(0)}G`;
  };

  return (
    <div className="hud-panel p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="hud-label flex items-center gap-2">
          <Trophy size={12} style={{ color: 'var(--color-accent)' }} />
          Savings Summary
        </h3>
        <button
          onClick={() => navigate('/leaderboard')}
          className="text-[10px] px-2 py-1 rounded-md transition-colors cursor-pointer"
          style={{
            background: 'var(--color-accent-subtle)',
            color: 'var(--color-accent)',
            border: '1px solid var(--color-accent)',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
        >
          View leaderboard →
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        <MetricBadge
          icon={TrendingDown}
          value={maxSaved > 0 ? `$${maxSaved.toFixed(2)}` : '$0.00'}
          label="dollars saved"
          color="var(--color-success)"
        />
        <MetricBadge
          icon={Zap}
          value={energyWhSaved >= 1000 ? `${(energyWhSaved / 1000).toFixed(2)} kWh` : `${energyWhSaved.toFixed(1)} Wh`}
          label="energy saved"
          color="#facc15"
        />
        <MetricBadge
          icon={Cpu}
          value={formatFlops(flopsGSaved)}
          label="FLOPs saved"
          color="#818cf8"
        />
        <MetricBadge
          icon={Hash}
          value={savings.total_tokens.toLocaleString()}
          label="total tokens"
          color="var(--color-text-secondary)"
        />
      </div>

      <div className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
        Across {savings.total_calls.toLocaleString()} requests vs the most expensive cloud provider.
        Energy &amp; FLOP estimates are approximate.
      </div>
    </div>
  );
}
