/**
 * OpenJarvis — Camera Vision Page
 *
 * Live webcam preview in the browser → snapshot → send to vision backend
 * via /api/jarvis/camera → display answer + optional TTS playback.
 *
 * Backend priority (auto-selected server-side):
 *   1. Intel NPU via OpenVINO GenAI (SmolVLM / Qwen2-VL)
 *   2. Ollama CPU (moondream / llava fallback)
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Camera, CameraOff, Loader2, Eye, Volume2, VolumeX,
  Wifi, WifiOff, RefreshCw, Send, Bot, Cpu, Zap,
} from 'lucide-react';
import { getBase } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CameraResult {
  response: string;
  model: string;
  backend: string;
  image_b64: string;
  audio_b64: string | null;
}

interface NpuStatus {
  openvino_installed: boolean;
  npu_present: boolean;
  devices: string[];
  best_device: string | null;
  model_ready: boolean;
  model_dir: string | null;
  active_device: string | null;
}

interface VisionStatus {
  ollamaRunning: boolean;
  recommended: string | null;
  vision_models: string[];
  npu: NpuStatus | null;
  activeBackend: 'npu' | 'ollama' | 'none';
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function checkVision(base: string): Promise<VisionStatus> {
  try {
    const r = await fetch(`${base}/api/jarvis/camera/models`);
    if (!r.ok) return { ollamaRunning: false, recommended: null, vision_models: [], npu: null, activeBackend: 'none' };
    const d = await r.json();
    return {
      ollamaRunning: d.ollama_running ?? false,
      recommended: d.recommended ?? null,
      vision_models: d.vision_models ?? [],
      npu: d.npu ?? null,
      activeBackend: d.active_backend ?? 'none',
    };
  } catch {
    return { ollamaRunning: false, recommended: null, vision_models: [], npu: null, activeBackend: 'none' };
  }
}

async function analyzeFrame(
  base: string,
  imageB64: string,
  question: string,
  tts: boolean,
  voice: string,
  model: string | null,
): Promise<CameraResult> {
  const body: Record<string, unknown> = { image_b64: imageB64, question, tts, voice };
  if (model) body.model = model;
  const r = await fetch(`${base}/api/jarvis/camera`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? r.statusText);
  }
  return r.json();
}

function playWav(b64: string) {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: 'audio/wav' });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.play().catch(() => {});
  audio.onended = () => URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CameraPage() {
  const base = getBase();

  // Webcam state
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // UI state
  const [question, setQuestion] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ttsOn, setTtsOn] = useState(true);
  const [voice, setVoice] = useState('hannah');

  // Results
  const [result, setResult] = useState<CameraResult | null>(null);
  const [history, setHistory] = useState<Array<{ question: string; result: CameraResult }>>([]);

  // Vision backend status
  const [visionStatus, setVisionStatus] = useState<VisionStatus>({
    ollamaRunning: false, recommended: null, vision_models: [], npu: null, activeBackend: 'none',
  });

  // Time
  const [time, setTime] = useState(() => new Date().toLocaleTimeString());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(t);
  }, []);

  // Check vision backends on mount and every 10s
  const refreshStatus = useCallback(async () => {
    const s = await checkVision(base);
    setVisionStatus(s);
  }, [base]);

  useEffect(() => {
    refreshStatus();
    const t = setInterval(refreshStatus, 10000);
    return () => clearInterval(t);
  }, [refreshStatus]);

  // Start webcam
  const startCamera = useCallback(async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setCameraActive(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setCameraError(`Camera error: ${msg}`);
    }
  }, []);

  // Stop webcam
  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraActive(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => () => stopCamera(), [stopCamera]);

  // Capture frame → analyze
  const handleAnalyze = useCallback(async () => {
    if (!cameraActive || !videoRef.current || !canvasRef.current) return;
    if (analyzing) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Get JPEG base64 (strip data:image/jpeg;base64, prefix)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    const imageB64 = dataUrl.split(',')[1];

    const q = question.trim() || 'Describe what you see in this image.';
    setAnalyzing(true);
    setError(null);

    try {
      const r = await analyzeFrame(
        base, imageB64, q, ttsOn, voice, visionStatus.recommended,
      );
      setResult(r);
      setHistory(prev => [{ question: q, result: r }, ...prev].slice(0, 10));
      if (ttsOn && r.audio_b64) playWav(r.audio_b64);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setAnalyzing(false);
    }
  }, [cameraActive, analyzing, question, base, ttsOn, voice, visionStatus.recommended]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAnalyze();
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const npuReady = visionStatus.npu?.model_ready ?? false;
  const ollamaOk = visionStatus.ollamaRunning && !!visionStatus.recommended;
  const anyBackendReady = npuReady || ollamaOk;
  const activeBackend = visionStatus.activeBackend;

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a0a0f 0%, #0f0f1a 50%, #0a0a0f 100%)',
      color: '#e2e8f0',
      fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* ── Status bar ── */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '8px 24px',
        borderBottom: '1px solid rgba(0,200,255,0.15)',
        background: 'rgba(0,0,0,0.4)',
        fontSize: '11px',
        letterSpacing: '0.1em',
        color: '#64748b',
      }}>
        <span style={{ color: '#00c8ff', fontWeight: 700 }}>OPENJARVIS · CAMERA VISION</span>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          {/* NPU indicator */}
          {visionStatus.npu && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4,
              color: npuReady ? '#a78bfa' : visionStatus.npu.npu_present ? '#fbbf24' : '#475569' }}>
              <Zap size={11} />
              {npuReady
                ? `NPU · ${visionStatus.npu.best_device}`
                : visionStatus.npu.npu_present
                  ? 'NPU DETECTED (no model)'
                  : 'NO NPU'}
            </span>
          )}
          {/* Ollama indicator */}
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: ollamaOk ? '#22c55e' : '#475569' }}>
            {ollamaOk ? <Wifi size={11} /> : <WifiOff size={11} />}
            {ollamaOk ? `OLLAMA · ${visionStatus.recommended}` : 'OLLAMA OFFLINE'}
          </span>
          {/* Active backend badge */}
          {anyBackendReady && (
            <span style={{ padding: '2px 8px', borderRadius: 10,
              background: activeBackend === 'npu' ? 'rgba(167,139,250,0.15)' : 'rgba(34,197,94,0.1)',
              color: activeBackend === 'npu' ? '#a78bfa' : '#22c55e', fontSize: 10, fontWeight: 700 }}>
              {activeBackend === 'npu' ? '⚡ NPU' : '🧠 CPU'}
            </span>
          )}
          <button onClick={refreshStatus} title="Refresh status" style={{
            background: 'none', border: 'none', color: '#475569', cursor: 'pointer', padding: 2,
          }}>
            <RefreshCw size={11} />
          </button>
          <span>{time}</span>
        </div>
      </div>

      {/* ── Main content ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── Left: camera + controls ── */}
        <div style={{
          flex: '0 0 600px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          padding: '24px 16px 24px 24px',
          borderRight: '1px solid rgba(0,200,255,0.1)',
        }}>

          {/* Camera preview */}
          <div style={{
            position: 'relative',
            background: '#000',
            borderRadius: 12,
            overflow: 'hidden',
            border: `2px solid ${cameraActive ? 'rgba(0,200,255,0.4)' : 'rgba(255,255,255,0.1)'}`,
            aspectRatio: '16/9',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: cameraActive ? '0 0 30px rgba(0,200,255,0.15)' : 'none',
          }}>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                display: cameraActive ? 'block' : 'none',
                transform: 'scaleX(-1)', // mirror for selfie
              }}
            />
            {!cameraActive && (
              <div style={{ textAlign: 'center', color: '#475569' }}>
                <CameraOff size={48} style={{ marginBottom: 12 }} />
                <div style={{ fontSize: 13 }}>Camera is off</div>
                {cameraError && (
                  <div style={{ color: '#ef4444', fontSize: 11, marginTop: 8, maxWidth: 300 }}>
                    {cameraError}
                  </div>
                )}
              </div>
            )}
            {/* Recording indicator */}
            {cameraActive && (
              <div style={{
                position: 'absolute', top: 12, right: 12,
                display: 'flex', alignItems: 'center', gap: 6,
                background: 'rgba(0,0,0,0.7)', borderRadius: 20,
                padding: '4px 10px', fontSize: 11, color: '#22c55e',
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: '#22c55e',
                  animation: 'pulse 1.5s infinite',
                }} />
                LIVE
              </div>
            )}
            {/* Analyzing overlay */}
            {analyzing && (
              <div style={{
                position: 'absolute', inset: 0,
                background: 'rgba(0,0,0,0.6)',
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 12,
              }}>
                <Loader2 size={36} color="#00c8ff" style={{ animation: 'spin 1s linear infinite' }} />
                <span style={{ fontSize: 13, color: '#94a3b8' }}>
                  Analyzing with {activeBackend === 'npu' ? `NPU · ${visionStatus.npu?.best_device}` : visionStatus.recommended ?? 'vision model'}…
                </span>
              </div>
            )}
          </div>

          {/* Hidden canvas for frame capture */}
          <canvas ref={canvasRef} style={{ display: 'none' }} />

          {/* Camera toggle button */}
          <button
            onClick={cameraActive ? stopCamera : startCamera}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              padding: '12px 24px', borderRadius: 10, border: 'none', cursor: 'pointer',
              background: cameraActive
                ? 'linear-gradient(135deg, #7f1d1d, #991b1b)'
                : 'linear-gradient(135deg, #164e63, #0e7490)',
              color: '#fff', fontSize: 14, fontWeight: 600,
              transition: 'all 0.2s',
            }}
          >
            {cameraActive ? <CameraOff size={18} /> : <Camera size={18} />}
            {cameraActive ? 'Stop Camera' : 'Start Camera'}
          </button>

          {/* Question input + analyze */}
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about what the camera sees… (Enter to analyze)"
              disabled={!cameraActive || analyzing}
              style={{
                flex: 1, padding: '12px 16px', borderRadius: 8, border: '1px solid rgba(0,200,255,0.2)',
                background: 'rgba(255,255,255,0.05)', color: '#e2e8f0', fontSize: 13,
                outline: 'none',
              }}
            />
            <button
              onClick={handleAnalyze}
              disabled={!cameraActive || analyzing || !anyBackendReady}
              title="Analyze frame"
              style={{
                padding: '12px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
                background: (!cameraActive || analyzing || !anyBackendReady)
                  ? 'rgba(0,200,255,0.1)'
                  : 'linear-gradient(135deg, #0e7490, #0891b2)',
                color: '#fff', transition: 'all 0.2s',
              }}
            >
              {analyzing ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={18} />}
            </button>
          </div>

          {/* Quick question presets */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {[
              'What do you see?',
              'Describe the scene',
              'What is in front of me?',
              'What am I holding?',
              'How many people are visible?',
              'Read any text you see',
              'Describe my surroundings',
            ].map(q => (
              <button
                key={q}
                onClick={() => { setQuestion(q); }}
                style={{
                  padding: '6px 12px', borderRadius: 20, border: '1px solid rgba(0,200,255,0.2)',
                  background: 'rgba(0,200,255,0.05)', color: '#94a3b8',
                  fontSize: 11, cursor: 'pointer', transition: 'all 0.15s',
                }}
                onMouseEnter={e => { (e.target as HTMLButtonElement).style.color = '#00c8ff'; }}
                onMouseLeave={e => { (e.target as HTMLButtonElement).style.color = '#94a3b8'; }}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Error */}
          {error && (
            <div style={{
              padding: '10px 14px', borderRadius: 8,
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
              color: '#fca5a5', fontSize: 12,
            }}>
              {error}
            </div>
          )}
        </div>

        {/* ── Right: settings + results ── */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', gap: 16,
          padding: '24px 24px 24px 16px', overflowY: 'auto',
        }}>

          {/* Settings panel */}
          <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(0,200,255,0.1)',
            borderRadius: 12, padding: '16px',
          }}>
            <div style={{ fontSize: 11, letterSpacing: '0.15em', color: '#00c8ff', marginBottom: 12, fontWeight: 700 }}>
              VISION SETTINGS
            </div>

            {/* NPU status */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>INTEL NPU (AI BOOST)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Zap size={14} color={npuReady ? '#a78bfa' : visionStatus.npu?.npu_present ? '#fbbf24' : '#475569'} />
                <span style={{ fontSize: 12, color: npuReady ? '#a78bfa' : visionStatus.npu?.npu_present ? '#fbbf24' : '#475569' }}>
                  {npuReady
                    ? `Active · ${visionStatus.npu?.best_device} · ${visionStatus.npu?.model_dir?.split(/[/\\]/).pop()}`
                    : visionStatus.npu?.npu_present
                      ? 'Detected — model not downloaded yet'
                      : visionStatus.npu?.openvino_installed
                        ? 'OpenVINO installed — NPU not found'
                        : 'OpenVINO not installed'}
                </span>
              </div>
              {visionStatus.npu && !npuReady && (
                <div style={{
                  marginTop: 8, padding: '8px 12px', borderRadius: 6,
                  background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.15)',
                  fontSize: 11, color: '#94a3b8',
                }}>
                  <div style={{ color: '#a78bfa', marginBottom: 4, fontWeight: 600 }}>Enable NPU acceleration:</div>
                  <div>Run <code style={{ color: '#a78bfa' }}>setup_openvino_npu.bat</code> in the project folder</div>
                  <div style={{ marginTop: 4, color: '#64748b' }}>Downloads SmolVLM-256M (~500 MB) and runs on your Intel AI Boost NPU</div>
                </div>
              )}
            </div>

            {/* Ollama status */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>OLLAMA (CPU FALLBACK)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Cpu size={14} color={ollamaOk ? '#22c55e' : '#475569'} />
                <span style={{ fontSize: 12, color: ollamaOk ? '#22c55e' : '#475569' }}>
                  {ollamaOk ? visionStatus.recommended : 'Not running'}
                </span>
              </div>
              {!ollamaOk && (
                <div style={{
                  marginTop: 8, padding: '8px 12px', borderRadius: 6,
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
                  fontSize: 11, color: '#64748b',
                }}>
                  <div>Run: <code style={{ color: '#94a3b8' }}>ollama pull moondream</code></div>
                </div>
              )}
              {ollamaOk && visionStatus.vision_models.length > 1 && (
                <div style={{ marginTop: 6, fontSize: 11, color: '#64748b' }}>
                  Other: {visionStatus.vision_models.filter(m => m !== visionStatus.recommended).join(', ')}
                </div>
              )}
            </div>

            {/* Active backend summary */}
            <div style={{ marginBottom: 14, padding: '8px 12px', borderRadius: 6,
              background: activeBackend === 'npu' ? 'rgba(167,139,250,0.08)' : activeBackend === 'ollama' ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
              border: `1px solid ${activeBackend === 'npu' ? 'rgba(167,139,250,0.2)' : activeBackend === 'ollama' ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.2)'}`,
            }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>ACTIVE BACKEND</div>
              <div style={{ fontSize: 13, fontWeight: 700,
                color: activeBackend === 'npu' ? '#a78bfa' : activeBackend === 'ollama' ? '#22c55e' : '#ef4444' }}>
                {activeBackend === 'npu' ? '⚡ Intel NPU (OpenVINO)' : activeBackend === 'ollama' ? '🧠 Ollama (CPU)' : '⚠ No backend ready'}
              </div>
            </div>

            {/* TTS toggle */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>Speak response (TTS)</span>
              <button
                onClick={() => setTtsOn(v => !v)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 12px', borderRadius: 20, border: 'none', cursor: 'pointer',
                  background: ttsOn ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.05)',
                  color: ttsOn ? '#22c55e' : '#64748b', fontSize: 11,
                }}
              >
                {ttsOn ? <Volume2 size={14} /> : <VolumeX size={14} />}
                {ttsOn ? 'ON' : 'OFF'}
              </button>
            </div>

            {/* Voice picker */}
            {ttsOn && (
              <div>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>TTS VOICE</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {['hannah', 'leah', 'jessica', 'zoe', 'mia', 'leo'].map(v => (
                    <button
                      key={v}
                      onClick={() => setVoice(v)}
                      style={{
                        padding: '4px 12px', borderRadius: 20,
                        border: `1px solid ${voice === v ? '#a78bfa' : 'rgba(255,255,255,0.1)'}`,
                        background: voice === v ? 'rgba(167,139,250,0.15)' : 'transparent',
                        color: voice === v ? '#a78bfa' : '#64748b', fontSize: 11, cursor: 'pointer',
                      }}
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Latest result */}
          {result && (
            <div style={{
              background: 'rgba(0,200,255,0.05)',
              border: '1px solid rgba(0,200,255,0.2)',
              borderRadius: 12, padding: '16px',
            }}>
              <div style={{ fontSize: 11, letterSpacing: '0.15em', color: '#00c8ff', marginBottom: 12, fontWeight: 700 }}>
                LATEST ANALYSIS
              </div>
              {/* Captured frame thumbnail */}
              {result.image_b64 && (
                <img
                  src={`data:image/jpeg;base64,${result.image_b64}`}
                  alt="Captured frame"
                  style={{
                    width: '100%', borderRadius: 8, marginBottom: 12,
                    border: '1px solid rgba(0,200,255,0.15)',
                    maxHeight: 200, objectFit: 'cover',
                  }}
                />
              )}
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <Eye size={16} color="#00c8ff" style={{ marginTop: 2, flexShrink: 0 }} />
                <p style={{ margin: 0, fontSize: 13, lineHeight: 1.7, color: '#e2e8f0' }}>
                  {result.response}
                </p>
              </div>
              <div style={{ marginTop: 8, fontSize: 10, color: '#475569', display: 'flex', gap: 12 }}>
                <span>Model: {result.model}</span>
                {result.backend && (
                  <span style={{ color: result.backend.startsWith('npu') ? '#a78bfa' : '#22c55e' }}>
                    Backend: {result.backend}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Conversation history */}
          {history.length > 0 && (
            <div style={{
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: '16px',
            }}>
              <div style={{ fontSize: 11, letterSpacing: '0.15em', color: '#475569', marginBottom: 12, fontWeight: 700 }}>
                HISTORY
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {history.slice(1).map((item, i) => (
                  <div key={i} style={{
                    borderLeft: '2px solid rgba(0,200,255,0.2)',
                    paddingLeft: 12,
                  }}>
                    <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>
                      <Bot size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      Q: {item.question}
                    </div>
                    <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>
                      {item.result.response.slice(0, 200)}{item.result.response.length > 200 ? '…' : ''}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Instructions if no result yet */}
          {!result && (
            <div style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
              textAlign: 'center', color: '#334155', padding: 40,
            }}>
              <div>
                <Camera size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
                <div style={{ fontSize: 14, marginBottom: 8 }}>Start the camera, then click Analyze</div>
                <div style={{ fontSize: 12, color: '#1e293b' }}>
                  Jarvis will use Ollama's local vision AI to answer your questions about what the camera sees.
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
      `}</style>
    </div>
  );
}
