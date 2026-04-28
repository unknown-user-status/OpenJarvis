/**
 * OpenJarvis — Voice Mode
 *
 * Features
 * --------
 * • Animated "reactor-core" orb that pulses while idle, glows while recording,
 *   and spins while Jarvis is thinking / speaking.
 * • Hold-to-record OR click-to-toggle mic button.
 * • Sends audio → /api/jarvis/voice  (STT → plugin/LLM dispatch)
 * • Optional TTS: plays back Groq Orpheus WAV audio via Web Audio API.
 * • Conversation history in a right-hand panel.
 * • Voice Mode Launcher: Launch standalone voice modes (v5, Deepgram)
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Mic, MicOff, Volume2, VolumeX, Loader2, Zap, StopCircle, X, Play, Square,
} from 'lucide-react';
import { getBase } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Phase = 'idle' | 'recording' | 'transcribing' | 'thinking' | 'speaking' | 'done' | 'error';

interface HistoryItem {
  id: string;
  you: string;
  jarvis: string;
  mode: 'plugin' | 'control' | 'qa';
  ts: number;
}

interface VoiceModeStatus {
  v5: { running: boolean; pid: number | null };
  deepgram: { running: boolean; pid: number | null };
}

const RECORD_SECONDS = 6;

// ---------------------------------------------------------------------------
// Voice Mode Launcher Component
// ---------------------------------------------------------------------------

function VoiceModeLauncher() {
  const [status, setStatus] = useState<VoiceModeStatus>({ v5: { running: false, pid: null }, deepgram: { running: false, pid: null } });
  const [loading, setLoading] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${getBase()}/api/voice/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data.modes || { v5: { running: false, pid: null }, deepgram: { running: false, pid: null } });
      }
    } catch {
      // Ignore errors
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const launchMode = async (mode: 'v5' | 'deepgram') => {
    setLoading(mode);
    try {
      const res = await fetch(`${getBase()}/api/voice/launch?mode=${mode}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        await fetchStatus();
      } else {
        alert(data.error || 'Failed to launch voice mode');
      }
    } catch {
      alert('Failed to launch voice mode');
    } finally {
      setLoading(null);
    }
  };

  const stopMode = async (mode: 'v5' | 'deepgram') => {
    setLoading(mode);
    try {
      const res = await fetch(`${getBase()}/api/voice/stop?mode=${mode}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        await fetchStatus();
      } else {
        alert(data.error || 'Failed to stop voice mode');
      }
    } catch {
      alert('Failed to stop voice mode');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Primary: Deepgram Voice */}
      <div className="rounded-xl p-6" style={{ background: 'linear-gradient(135deg, var(--color-accent-subtle) 0%, var(--color-bg-secondary) 100%)', border: '2px solid var(--color-accent)' }}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg" style={{ background: 'var(--color-accent)' }}>
                <Volume2 size={20} style={{ color: 'white' }} />
              </div>
              <div>
                <h2 className="text-lg font-bold" style={{ color: 'var(--color-text)' }}>Deepgram Voice</h2>
                <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>Continuous two-way voice conversation</p>
              </div>
            </div>
            <p className="text-sm mb-4" style={{ color: 'var(--color-text-secondary)' }}>
              Speak naturally — Jarvis listens, thinks, and responds with voice. Full machine control and web research capabilities.
            </p>
          </div>
          <div className={`text-xs px-3 py-1 rounded-full font-medium ${status.deepgram.running ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/20 text-gray-500'}`}>
            {status.deepgram.running ? '● Running' : '○ Stopped'}
          </div>
        </div>
        {status.deepgram.running ? (
          <button
            onClick={() => stopMode('deepgram')}
            disabled={loading === 'deepgram'}
            className="w-full flex items-center justify-center gap-2 text-sm px-6 py-3 rounded-lg font-medium transition-colors cursor-pointer"
            style={{
              background: 'var(--color-error)',
              color: 'white',
              opacity: loading === 'deepgram' ? 0.6 : 1,
            }}
          >
            {loading === 'deepgram' ? <Loader2 size={16} className="animate-spin" /> : <Square size={16} />}
            Stop Deepgram Voice
          </button>
        ) : (
          <button
            onClick={() => launchMode('deepgram')}
            disabled={loading === 'deepgram'}
            className="w-full flex items-center justify-center gap-2 text-sm px-6 py-3 rounded-lg font-medium transition-colors cursor-pointer"
            style={{
              background: 'var(--color-accent)',
              color: 'white',
              opacity: loading === 'deepgram' ? 0.6 : 1,
            }}
          >
            {loading === 'deepgram' ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            Launch Deepgram Voice
          </button>
        )}
      </div>

      {/* Secondary: Voice Mode v5 */}
      <div className="rounded-xl p-4" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg" style={{ background: 'var(--color-bg-tertiary)' }}>
              <Mic size={16} style={{ color: 'var(--color-text-secondary)' }} />
            </div>
            <div>
              <h3 className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>Voice Mode v5</h3>
              <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>Local VAD-based voice control</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={`text-[10px] px-2 py-0.5 rounded-full ${status.v5.running ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/20 text-gray-500'}`}>
              {status.v5.running ? 'Running' : 'Stopped'}
            </div>
            {status.v5.running ? (
              <button
                onClick={() => stopMode('v5')}
                disabled={loading === 'v5'}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                style={{
                  background: 'var(--color-error-subtle)',
                  border: '1px solid var(--color-error)',
                  color: 'var(--color-error)',
                  opacity: loading === 'v5' ? 0.6 : 1,
                }}
              >
                {loading === 'v5' ? <Loader2 size={12} className="animate-spin" /> : <Square size={12} />}
                Stop
              </button>
            ) : (
              <button
                onClick={() => launchMode('v5')}
                disabled={loading === 'v5'}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                style={{
                  background: 'var(--color-bg-tertiary)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-secondary)',
                  opacity: loading === 'v5' ? 0.6 : 1,
                }}
              >
                {loading === 'v5' ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                Launch
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Animated orb
// ---------------------------------------------------------------------------

function JarvisOrb({ phase }: { phase: Phase }) {
  const isRecording  = phase === 'recording';
  const isThinking   = phase === 'transcribing' || phase === 'thinking';
  const isSpeaking   = phase === 'speaking';
  const isDone       = phase === 'done';
  const isError      = phase === 'error';

  const coreColor = isError
    ? '#ef4444'
    : isRecording
    ? '#f97316'
    : isThinking
    ? '#a78bfa'
    : isSpeaking
    ? '#34d399'
    : '#0891b2';

  return (
    <div className="relative flex items-center justify-center" style={{ width: 180, height: 180 }}>
      {/* Outer glow rings */}
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="absolute rounded-full"
          style={{
            width: 180 - (i - 1) * 0,
            height: 180 - (i - 1) * 0,
            border: `1px solid ${coreColor}`,
            opacity: isRecording || isSpeaking ? 0.35 / i : 0.15 / i,
            transform: `scale(${1 + i * 0.18})`,
            animation: isRecording || isSpeaking
              ? `orb-ring-pulse ${1.2 + i * 0.3}s ease-in-out infinite alternate`
              : 'none',
            transition: 'all 0.4s ease',
          }}
        />
      ))}

      {/* Mid ring */}
      <div
        className="absolute rounded-full"
        style={{
          width: 148,
          height: 148,
          border: `2px solid ${coreColor}`,
          opacity: 0.4,
          animation: isThinking
            ? 'orb-spin 2s linear infinite'
            : isRecording
            ? 'orb-spin 1s linear infinite'
            : 'none',
          transition: 'opacity 0.3s',
        }}
      />

      {/* Inner core */}
      <div
        className="absolute rounded-full flex items-center justify-center"
        style={{
          width: 120,
          height: 120,
          background: `radial-gradient(circle at 38% 38%, ${coreColor}44, ${coreColor}11 70%)`,
          border: `2px solid ${coreColor}88`,
          boxShadow: `0 0 ${isRecording || isSpeaking ? 40 : 16}px ${coreColor}55`,
          transition: 'all 0.4s ease',
          animation: isRecording || isSpeaking
            ? 'orb-core-pulse 0.8s ease-in-out infinite alternate'
            : 'none',
        }}
      >
        {/* Hex grid overlay */}
        <svg width="80" height="80" viewBox="0 0 80 80" style={{ opacity: 0.18, position: 'absolute' }}>
          <pattern id="hex" x="0" y="0" width="20" height="17.32" patternUnits="userSpaceOnUse">
            <polygon points="10,0 20,5 20,15 10,20 0,15 0,5" fill="none" stroke={coreColor} strokeWidth="0.5" />
          </pattern>
          <rect width="80" height="80" fill="url(#hex)" />
        </svg>

        {/* Center icon */}
        <div style={{ position: 'relative', zIndex: 1 }}>
          {isThinking ? (
            <Loader2 size={32} color={coreColor} className="animate-spin" />
          ) : isRecording ? (
            <StopCircle size={32} color={coreColor} />
          ) : isError ? (
            <X size={32} color={coreColor} />
          ) : (
            <Mic size={32} color={coreColor} />
          )}
        </div>
      </div>

      {/* Scanning arc */}
      {(isThinking || isSpeaking) && (
        <svg
          className="absolute"
          width="180"
          height="180"
          viewBox="0 0 180 180"
          style={{ animation: 'orb-spin 3s linear infinite' }}
        >
          <circle
            cx="90"
            cy="90"
            r="82"
            fill="none"
            stroke={coreColor}
            strokeWidth="2"
            strokeDasharray="60 460"
            strokeLinecap="round"
            opacity="0.6"
          />
        </svg>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Waveform bars (shown when recording)
// ---------------------------------------------------------------------------

function WaveBars({ active }: { active: boolean }) {
  const [bars, setBars] = useState<number[]>(Array(28).fill(4));
  const animRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (active) {
      animRef.current = setInterval(() => {
        setBars(Array(28).fill(0).map(() => 4 + Math.random() * 28));
      }, 60);
    } else {
      if (animRef.current) clearInterval(animRef.current);
      setBars(Array(28).fill(4));
    }
    return () => { if (animRef.current) clearInterval(animRef.current); };
  }, [active]);

  return (
    <div className="flex items-end gap-[2px]" style={{ height: 40 }}>
      {bars.map((h, i) => (
        <div
          key={i}
          className="rounded-full transition-all duration-75"
          style={{
            width: 3,
            height: active ? h : 4,
            background: active ? 'var(--color-accent)' : 'var(--color-border)',
          }}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main VoicePage
// ---------------------------------------------------------------------------

export function VoicePage() {
  const [phase, setPhase]         = useState<Phase>('idle');
  const [countdown, setCountdown] = useState(RECORD_SECONDS);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse]   = useState('');
  const [mode, setMode]           = useState<'plugin' | 'control' | 'qa'>('qa');
  const [history, setHistory]     = useState<HistoryItem[]>([]);
  const [error, setError]         = useState('');
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [voice, setVoice]         = useState('hannah');

  const mediaRef  = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef  = useRef<HTMLAudioElement | null>(null);

  // Play back WAV base64 audio
  const playAudio = useCallback((b64: string) => {
    try {
      const binary = atob(b64);
      const bytes  = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: 'audio/wav' });
      const url  = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.pause();
        URL.revokeObjectURL(audioRef.current.src);
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      setPhase('speaking');
      audio.onended = () => {
        setPhase('done');
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => setPhase('done');
      audio.play().catch(() => setPhase('done'));
    } catch {
      setPhase('done');
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    mediaRef.current?.stop();
  }, []);

  const startRecording = useCallback(async () => {
    setError('');
    setTranscript('');
    setResponse('');
    setPhase('recording');
    setCountdown(RECORD_SECONDS);

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError('Microphone access denied.');
      setPhase('error');
      return;
    }

    chunksRef.current = [];
    const recorder = new MediaRecorder(stream);
    mediaRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
      setPhase('transcribing');

      try {
        const fd = new FormData();
        fd.append('audio', blob, 'recording.webm');
        // Ask for TTS audio back if enabled
        const url = `${getBase()}/api/jarvis/voice?tts=${ttsEnabled}&voice=${voice}`;
        const res = await fetch(url, { method: 'POST', body: fd });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(detail.detail || `Server error ${res.status}`);
        }
        const data = await res.json();

        setTranscript(data.transcript || '');
        setMode(data.mode || 'qa');
        setResponse(data.response || '');
        setPhase('thinking');

        setHistory((h) => [
          {
            id: Date.now().toString(36),
            you: data.transcript || '',
            jarvis: data.response || '',
            mode: data.mode || 'qa',
            ts: Date.now(),
          },
          ...h.slice(0, 49),
        ]);

        if (ttsEnabled && data.audio_b64) {
          playAudio(data.audio_b64);
        } else {
          setPhase('done');
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        setPhase('error');
      }
    };

    recorder.start();

    let remaining = RECORD_SECONDS;
    timerRef.current = setInterval(() => {
      remaining -= 1;
      setCountdown(remaining);
      if (remaining <= 0) {
        clearInterval(timerRef.current!);
        stopRecording();
      }
    }, 1000);
  }, [stopRecording, ttsEnabled, voice, playAudio]);

  const handleOrbClick = () => {
    if (phase === 'recording') { stopRecording(); return; }
    if (phase === 'speaking')  { audioRef.current?.pause(); setPhase('done'); return; }
    if (['idle', 'done', 'error'].includes(phase)) startRecording();
  };

  const isRecording = phase === 'recording';
  const isWorking   = phase === 'transcribing' || phase === 'thinking';

  const phaseLabel: Record<Phase, string> = {
    idle:         'Click the orb to speak',
    recording:    `Listening… ${countdown}s`,
    transcribing: 'Transcribing…',
    thinking:     'Jarvis is thinking…',
    speaking:     'Jarvis is speaking…',
    done:         'Click the orb to speak again',
    error:        error || 'Error occurred',
  };

  const modeBadge = {
    plugin:  { label: 'Plugin', color: 'var(--color-accent)' },
    control: { label: 'Desktop Control', color: 'var(--color-accent-amber)' },
    qa:      { label: 'AI Answer', color: 'var(--color-accent-purple)' },
  } as const;

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Main panel ── */}
      <div className="flex-1 flex flex-col items-center overflow-y-auto px-6 py-10">
        <div className="w-full max-w-xl">

          {/* Header */}
          <div className="mb-6 text-center">
            <h1 className="text-3xl font-bold mb-1" style={{ color: 'var(--color-text)', fontFamily: 'var(--font-display)' }}>
              OpenJarvis Voice
            </h1>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Continuous two-way voice conversation with full AI capabilities
            </p>
          </div>

          {/* Voice Mode Launcher */}
          <VoiceModeLauncher />

          {/* Divider */}
          <div className="flex items-center gap-3 my-8">
            <div className="flex-1 h-px" style={{ background: 'var(--color-border)' }} />
            <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>OR</span>
            <div className="flex-1 h-px" style={{ background: 'var(--color-border)' }} />
          </div>

          {/* Legacy Web Voice */}
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-widest mb-4 text-center" style={{ color: 'var(--color-text-tertiary)' }}>
              Legacy Web Voice (Hold-to-Record)
            </p>
          </div>

          {/* Orb + waveform */}
          <div className="flex flex-col items-center gap-6 mb-8">
            <button
              onClick={handleOrbClick}
              disabled={isWorking}
              className="transition-transform duration-150 focus:outline-none"
              style={{
                cursor: isWorking ? 'default' : 'pointer',
                opacity: isWorking ? 0.85 : 1,
                transform: isWorking ? 'scale(0.97)' : 'scale(1)',
              }}
              aria-label={isRecording ? 'Stop recording' : 'Start recording'}
            >
              <JarvisOrb phase={phase} />
            </button>

            <WaveBars active={isRecording} />

            {/* Phase label */}
            <p
              className="text-sm font-medium tracking-wide"
              style={{ color: phase === 'error' ? 'var(--color-error)' : 'var(--color-text-secondary)' }}
            >
              {phaseLabel[phase]}
            </p>

            {/* TTS / voice controls */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setTtsEnabled((v) => !v)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition-colors cursor-pointer"
                style={{
                  background: ttsEnabled ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
                  border: `1px solid ${ttsEnabled ? 'var(--color-accent)' : 'var(--color-border)'}`,
                  color: ttsEnabled ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                }}
              >
                {ttsEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />}
                {ttsEnabled ? 'Voice ON' : 'Voice OFF'}
              </button>

              {ttsEnabled && (
                <select
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                  className="text-xs px-2 py-1.5 rounded-lg outline-none cursor-pointer"
                  style={{
                    background: 'var(--color-bg-secondary)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  {['hannah', 'autumn', 'diana', 'austin', 'daniel', 'troy'].map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Transcript + response bubbles */}
          {(transcript || response) && (
            <div className="flex flex-col gap-3 mb-8">
              {transcript && (
                <div
                  className="rounded-xl px-4 py-3"
                  style={{ background: 'var(--color-accent-subtle)', border: '1px solid var(--color-accent-subtle)' }}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Mic size={12} style={{ color: 'var(--color-accent)' }} />
                    <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--color-accent)' }}>
                      You
                    </span>
                  </div>
                  <p className="text-sm" style={{ color: 'var(--color-text)' }}>{transcript}</p>
                </div>
              )}

              {response && (
                <div
                  className="rounded-xl px-4 py-3"
                  style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Volume2 size={12} style={{ color: 'var(--color-text-secondary)' }} />
                    <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--color-text-secondary)' }}>
                      Jarvis
                    </span>
                    <span
                      className="text-[10px] px-2 py-0.5 rounded-full font-medium ml-1"
                      style={{
                        background: `${modeBadge[mode].color}18`,
                        color: modeBadge[mode].color,
                        border: `1px solid ${modeBadge[mode].color}44`,
                      }}
                    >
                      {mode === 'control' && <Zap size={8} className="inline mr-0.5" />}
                      {modeBadge[mode].label}
                    </span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--color-text)' }}>{response}</p>
                </div>
              )}
            </div>
          )}

          {/* Quick-commands grid */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--color-text-tertiary)' }}>
              Example commands
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                'What time is it', 'Show me the news', 'Weather in Tokyo',
                'Tell me about black holes', 'System status', 'Volume up',
                'Take a screenshot', 'Play lofi music', 'Tell a joke',
                'Remember my name is Alex', 'What do you know about me',
              ].map((cmd) => (
                <button
                  key={cmd}
                  className="text-xs px-3 py-1.5 rounded-full transition-colors cursor-pointer"
                  style={{
                    background: 'var(--color-bg-secondary)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text-secondary)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
                >
                  {cmd}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── History sidebar ── */}
      {history.length > 0 && (
        <div
          className="w-72 shrink-0 flex flex-col overflow-hidden"
          style={{ borderLeft: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
        >
          <div className="px-4 py-3 shrink-0 flex items-center justify-between" style={{ borderBottom: '1px solid var(--color-border)' }}>
            <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>History</h2>
            <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{history.length}</span>
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2 flex flex-col gap-2">
            {history.map((item) => (
              <div
                key={item.id}
                className="rounded-lg px-3 py-2.5 text-xs"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  {item.mode === 'control' ? (
                    <Zap size={10} style={{ color: 'var(--color-accent-amber)' }} />
                  ) : item.mode === 'plugin' ? (
                    <Volume2 size={10} style={{ color: 'var(--color-accent)' }} />
                  ) : (
                    <MicOff size={10} style={{ color: 'var(--color-accent-purple)' }} />
                  )}
                  <span className="font-medium truncate" style={{ color: 'var(--color-text)' }}>{item.you}</span>
                </div>
                <p className="line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>{item.jarvis}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CSS keyframe animations injected once */}
      <style>{`
        @keyframes orb-ring-pulse {
          from { opacity: 0.08; transform: scale(1.18); }
          to   { opacity: 0.30; transform: scale(1.26); }
        }
        @keyframes orb-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes orb-core-pulse {
          from { box-shadow: 0 0 20px var(--color-accent)44; }
          to   { box-shadow: 0 0 45px var(--color-accent)88; }
        }
      `}</style>
    </div>
  );
}
