import React, { useState, useEffect } from 'react';
import { Brain, Play, Settings, TrendingUp, Zap, Target, Users, Activity, CheckCircle, AlertCircle } from 'lucide-react';
import { fetchLearningStats, fetchLearningPolicy, triggerLearning } from '../../lib/api';

interface LearningStats {
  skill_discovery?: {
    available: boolean;
    discovered_count: number;
  };
}

interface LearningPolicy {
  enabled: boolean;
  update_interval: number;
  auto_update: boolean;
  routing: {
    policy: string;
    min_samples: number;
  };
  intelligence: {
    policy: string;
  };
  agent: {
    policy: string;
  };
  metrics: {
    accuracy_weight: number;
    latency_weight: number;
    cost_weight: number;
    efficiency_weight: number;
  };
}

export function LearningPanel() {
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [policy, setPolicy] = useState<LearningPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [lastResult, setLastResult] = useState<any>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [statsData, policyData] = await Promise.all([
        fetchLearningStats(),
        fetchLearningPolicy(),
      ]);
      setStats(statsData);
      setPolicy(policyData);
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Failed to load learning data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTriggerLearning = async () => {
    try {
      setTriggering(true);
      const result = await triggerLearning();
      if (result.success) {
        setLastResult(result.result);
        setError(null);
        // Reload data after trigger
        setTimeout(loadData, 1000);
      } else {
        setError(result.error || 'Failed to trigger learning');
      }
    } catch (e: any) {
      setError(e.message || 'Failed to trigger learning');
    } finally {
      setTriggering(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center space-x-2 mb-4">
          <Brain className="w-5 h-5 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900">Learning System</h3>
        </div>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Brain className="w-5 h-5 text-purple-600" />
          <h3 className="text-lg font-medium text-gray-900">Learning System</h3>
          {policy?.enabled ? (
            <CheckCircle size={16} className="text-green-500" />
          ) : (
            <AlertCircle size={16} className="text-yellow-500" />
          )}
        </div>
        <button
          onClick={handleTriggerLearning}
          disabled={triggering || !policy?.enabled}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {triggering ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Running...
            </>
          ) : (
            <>
              <Play size={14} />
              Trigger Update
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {lastResult && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-sm text-green-800 font-medium mb-1">Learning Update Completed</p>
          <div className="text-xs text-green-700 space-y-1">
            {lastResult.traces_processed && (
              <p>Processed {lastResult.traces_processed} traces</p>
            )}
            {lastResult.improvement && (
              <p>Improvement: {(lastResult.improvement * 100).toFixed(2)}%</p>
            )}
            {lastResult.models_updated && lastResult.models_updated.length > 0 && (
              <p>Updated models: {lastResult.models_updated.join(', ')}</p>
            )}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {/* Status Overview */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center gap-2 mb-2">
              <Settings className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-medium text-gray-900">System Status</span>
            </div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Enabled:</span>
                <span style={{ color: policy?.enabled ? 'var(--color-success)' : 'var(--color-text-secondary)' }}>
                  {policy?.enabled ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Auto Update:</span>
                <span style={{ color: policy?.auto_update ? 'var(--color-success)' : 'var(--color-text-secondary)' }}>
                  {policy?.auto_update ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Update Interval:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {policy?.update_interval || 0}s
                </span>
              </div>
            </div>
          </div>

          <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-green-600" />
              <span className="text-sm font-medium text-gray-900">Skill Discovery</span>
            </div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Available:</span>
                <span style={{ color: stats?.skill_discovery?.available ? 'var(--color-success)' : 'var(--color-text-secondary)' }}>
                  {stats?.skill_discovery?.available ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Discovered:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {stats?.skill_discovery?.discovered_count || 0} skills
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Policy Configuration */}
        <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-purple-600" />
            <span className="text-sm font-medium text-gray-900">Active Policies</span>
          </div>
          <div className="grid grid-cols-3 gap-4 text-xs">
            <div>
              <span style={{ color: 'var(--color-text-tertiary)' }}>Routing:</span>
              <p className="font-medium mt-1" style={{ color: 'var(--color-text)' }}>
                {policy?.routing?.policy || 'N/A'}
              </p>
              {policy?.routing?.min_samples && (
                <p style={{ color: 'var(--color-text-tertiary)' }}>
                  Min samples: {policy.routing.min_samples}
                </p>
              )}
            </div>
            <div>
              <span style={{ color: 'var(--color-text-tertiary)' }}>Intelligence:</span>
              <p className="font-medium mt-1" style={{ color: 'var(--color-text)' }}>
                {policy?.intelligence?.policy || 'N/A'}
              </p>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-tertiary)' }}>Agent:</span>
              <p className="font-medium mt-1" style={{ color: 'var(--color-text)' }}>
                {policy?.agent?.policy || 'N/A'}
              </p>
            </div>
          </div>
        </div>

        {/* Metrics Weights */}
        {policy?.metrics && (
          <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center gap-2 mb-3">
              <Activity className="w-4 h-4 text-orange-600" />
              <span className="text-sm font-medium text-gray-900">Metrics Weights</span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Accuracy:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {(policy.metrics.accuracy_weight * 100).toFixed(0)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Latency:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {(policy.metrics.latency_weight * 100).toFixed(0)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Cost:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {(policy.metrics.cost_weight * 100).toFixed(0)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-tertiary)' }}>Efficiency:</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {(policy.metrics.efficiency_weight * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">
          The learning system continuously improves routing policies, intelligence configurations, and agent behaviors based on usage traces.
          <br />
          <a
            href="https://open-jarvis.github.io/OpenJarvis/learning/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-700"
          >
            Learn more about learning →
          </a>
        </p>
      </div>
    </div>
  );
}