import React, { useState, useEffect } from 'react';
import { Cpu, Zap, Settings as SettingsIcon, Check, AlertCircle } from 'lucide-react';

interface NPUConfig {
  device: string;
  load_in_8bit: boolean;
  cache_dir: string;
  model_path: string;
}

export function NPUConfigPanel() {
  const [config, setConfig] = useState<NPUConfig>({
    device: 'CPU',
    load_in_8bit: true,
    cache_dir: '',
    model_path: 'microsoft/phi-3-mini-4k-instruct',
  });
  
  const [isAvailable, setIsAvailable] = useState<boolean | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    checkNPUAvailability();
    loadConfig();
  }, []);

  const checkNPUAvailability = async () => {
    try {
      const response = await fetch('http://localhost:8000/v1/intelligence/hardware');
      const data = await response.json();
      // Check if Intel GPU/NPU is available
      const hasIntelNPU = data.gpu_name?.toLowerCase().includes('intel') || 
                         data.platform === 'Windows';
      setIsAvailable(hasIntelNPU);
    } catch {
      setIsAvailable(false);
    }
  };

  const loadConfig = () => {
    try {
      const saved = localStorage.getItem('openjarvis_npu_config');
      if (saved) {
        setConfig(JSON.parse(saved));
      }
    } catch {
      // Use defaults
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      localStorage.setItem('openjarvis_npu_config', JSON.stringify(config));
      setSaveMessage('Configuration saved successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch {
      setSaveMessage('Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const deviceOptions = [
    { value: 'CPU', label: 'CPU (General Purpose)', description: 'Run on CPU cores' },
    { value: 'GPU', label: 'GPU (Graphics)', description: 'Intel integrated graphics' },
    { value: 'NPU', label: 'NPU (Neural Processing)', description: 'AI accelerator if available' },
    { value: 'AUTO', label: 'AUTO', description: 'Let OpenVINO choose best device' },
  ];

  return (
    <div className="space-y-4">
      {/* Availability Status */}
      <div className="flex items-center gap-3 p-3 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
        {isAvailable === null ? (
          <AlertCircle size={20} style={{ color: 'var(--color-text-tertiary)' }} />
        ) : isAvailable ? (
          <Zap size={20} style={{ color: 'var(--color-success)' }} />
        ) : (
          <Cpu size={20} style={{ color: 'var(--color-text-tertiary)' }} />
        )}
        <div>
          <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            Intel NPU Status
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {isAvailable === null ? 'Checking...' : isAvailable ? 'NPU Available' : 'NPU Not Detected'}
          </div>
        </div>
      </div>

      {/* Device Selection */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text)' }}>
          Target Device
        </label>
        <select
          value={config.device}
          onChange={(e) => setConfig({ ...config, device: e.target.value })}
          className="w-full px-3 py-2 rounded-lg text-sm"
          style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
        >
          {deviceOptions.map(option => (
            <option key={option.value} value={option.value}>
              {option.label} - {option.description}
            </option>
          ))}
        </select>
      </div>

      {/* Model Selection */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text)' }}>
          Default Model
        </label>
        <select
          value={config.model_path}
          onChange={(e) => setConfig({ ...config, model_path: e.target.value })}
          className="w-full px-3 py-2 rounded-lg text-sm"
          style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
        >
          <option value="microsoft/phi-3-mini-4k-instruct">Phi-3 Mini 4K (Recommended)</option>
          <option value="TinyLlama/TinyLlama-1.1B">TinyLlama 1.1B (Fastest)</option>
          <option value="google/gemma-2b">Gemma 2B (Creative)</option>
          <option value="meta-llama/Llama-3.2-3B">Llama 3.2 3B (Balanced)</option>
        </select>
      </div>

      {/* Quantization Toggle */}
      <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
        <div>
          <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            INT8 Quantization
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            Reduces memory usage by ~50% with minimal accuracy loss
          </div>
        </div>
        <button
          onClick={() => setConfig({ ...config, load_in_8bit: !config.load_in_8bit })}
          className={`w-12 h-6 rounded-full transition-colors ${
            config.load_in_8bit ? 'opacity-100' : 'opacity-50'
          }`}
          style={{
            background: config.load_in_8bit ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
          }}
        >
          <div
            className={`w-5 h-5 rounded-full bg-white shadow transition-transform ${
              config.load_in_8bit ? 'translate-x-6' : 'translate-x-0.5'
            }`}
          />
        </button>
      </div>

      {/* Cache Directory */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text)' }}>
          Cache Directory
        </label>
        <input
          type="text"
          value={config.cache_dir}
          onChange={(e) => setConfig({ ...config, cache_dir: e.target.value })}
          placeholder="Default: ~/.openjarvis/openvino_cache"
          className="w-full px-3 py-2 rounded-lg text-sm"
          style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
        />
        <div className="text-xs mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
          Leave empty for default location
        </div>
      </div>

      {/* Save Button */}
      <div className="flex items-center justify-between">
        <div className="text-xs" style={{ color: saveMessage.includes('Failed') ? 'var(--color-error)' : 'var(--color-success)' }}>
          {saveMessage}
        </div>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-50"
          style={{ background: 'var(--color-accent)', color: 'white' }}
          onMouseEnter={(e) => isSaving || (e.currentTarget.style.opacity = '0.9')}
          onMouseLeave={(e) => isSaving || (e.currentTarget.style.opacity = '1')}
        >
          {isSaving ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Check size={16} />
              Save Configuration
            </>
          )}
        </button>
      </div>

      {/* Installation Instructions */}
      {!isAvailable && isAvailable !== null && (
        <div className="p-3 rounded-lg text-xs" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)' }}>
          <div className="font-medium mb-2" style={{ color: 'var(--color-text)' }}>
            Installation Required
          </div>
          <p className="mb-2">
            Install OpenVINO dependencies:
          </p>
          <code className="block p-2 rounded bg-black bg-opacity-20">
            pip install openvino openvino-dev[onnx,tensorflow2,pytorch] transformers optimum[openvino]
          </code>
        </div>
      )}
    </div>
  );
}