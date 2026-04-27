import React, { useState, useEffect } from 'react';
import { Cpu, HardDrive, Zap, Monitor, Activity } from 'lucide-react';
import { fetchHardwareInfo } from '../../lib/api';

interface HardwareInfo {
  platform: string;
  cpu: string;
  cpu_cores: number;
  ram_gb: number;
  ram_available_gb: number;
  gpu_name: string;
  vram_gb: number;
  recommended_tier: string;
  recommended_model: string;
}

export const HardwarePanel: React.FC = () => {
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const data = await fetchHardwareInfo();
        setHardware(data);
        setError(null);
      } catch (e: any) {
        setError(e.message || 'Failed to load hardware info');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center space-x-2 mb-4">
          <Monitor className="w-5 h-5 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900">Hardware Info</h3>
        </div>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  if (error || !hardware) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center space-x-2 mb-4">
          <Monitor className="w-5 h-5 text-red-500" />
          <h3 className="text-lg font-medium text-gray-900">Hardware Info</h3>
        </div>
        <p className="text-sm text-red-600">{error || 'No hardware data available'}</p>
      </div>
    );
  }

  const getTierColor = (tier: string) => {
    switch (tier) {
      case 'large': return 'text-green-600 bg-green-50';
      case 'medium': return 'text-blue-600 bg-blue-50';
      case 'small': return 'text-yellow-600 bg-yellow-50';
      case 'tiny': return 'text-orange-600 bg-orange-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Monitor className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-medium text-gray-900">Hardware Info</h3>
        </div>
        <span className={`px-2 py-1 text-xs font-medium rounded-full ${getTierColor(hardware.recommended_tier)}`}>
          {hardware.recommended_tier}
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">Platform</span>
          </div>
          <span className="text-sm font-medium text-gray-900">{hardware.platform}</span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">CPU</span>
          </div>
          <span className="text-sm font-medium text-gray-900">
            {hardware.cpu} ({hardware.cpu_cores} cores)
          </span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <HardDrive className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">RAM</span>
          </div>
          <span className="text-sm font-medium text-gray-900">
            {hardware.ram_gb} GB total ({hardware.ram_available_gb} GB available)
          </span>
        </div>

        {hardware.gpu_name && (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Monitor className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-600">GPU</span>
            </div>
            <span className="text-sm font-medium text-gray-900">
              {hardware.gpu_name} ({hardware.vram_gb} GB VRAM)
            </span>
          </div>
        )}

        <div className="pt-3 border-t border-gray-100">
          <div className="flex items-center space-x-2 mb-2">
            <Zap className="w-4 h-4 text-yellow-500" />
            <span className="text-sm font-medium text-gray-900">Recommended Model</span>
          </div>
          <p className="text-sm text-gray-600">{hardware.recommended_model}</p>
        </div>
      </div>
    </div>
  );
};