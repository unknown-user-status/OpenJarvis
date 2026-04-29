/**
 * OpenJarvis — Main HUD Page
 *
 * A JARVIS-style interface with:
 * • Top status bar (time, API health)
 * • Central animated orb that reacts to voice / chat state
 * • Waveform visualiser during recording
 * • Text chat input + microphone button (both in one bar)
 * • Conversation feed (chat bubbles)
 * • Right-hand capability quick-access panel
 * • TTS voice response — plays Groq Orpheus WAV
 * • Always-on voice mode using Web Speech API
 */

import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react';

// Web Speech API type declaration
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

type SpeechRecognition = any;
import {
  Mic, MicOff, Send, Volume2, VolumeX, Loader2, Zap, Bot,
  Clock, Wifi, WifiOff, StopCircle, ChevronRight,
} from 'lucide-react';
import { getBase } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Phase = 'idle' | 'recording' | 'transcribing' | 'thinking' | 'speaking' | 'done' | 'error';
type VoiceMode = 'push-to-talk' | 'always-on' | 'deepgram';

interface Message {
  id: string;
  role: 'user' | 'jarvis';
  content: string;
  mode?: 'plugin' | 'control' | 'qa';
  ts: number;
  promptTokens?: number;
  completionTokens?: number;
}

const RECORD_SECONDS = 6;
const QUICK_COMMANDS = [
  { label: 'Current time', cmd: 'What time is it' },
  { label: 'Top news', cmd: 'Show me the news' },
  { label: 'Weather', cmd: 'Weather in my city' },
  { label: 'System status', cmd: 'System info' },
  { label: 'Tell a joke', cmd: 'Tell me a joke' },
  { label: 'Wikipedia', cmd: 'Tell me about quantum computing' },
  { label: 'Volume up', cmd: 'Volume up' },
  { label: 'Screenshot', cmd: 'Take a screenshot' },
];

// ---------------------------------------------------------------------------
// Animated orb (same component as VoicePage for consistency)
// ---------------------------------------------------------------------------

function JarvisOrb({ phase, size = 160 }: { phase: Phase; size?: number }) {
  const isRecording = phase === 'recording';
  const isThinking  = phase === 'transcribing' || phase === 'thinking';
  const isSpeaking  = phase === 'speaking';
  const isError     = phase === 'error';

  const color = isError
    ? '#ef4444'
    : isRecording
    ? '#f97316'
    : isThinking
    ? '#a78bfa'
    : isSpeaking
    ? '#34d399'
    : '#0891b2';

  const s = size;
  const mid = s * 0.82;
  const core = s * 0.67;

  return (
    <div className="relative flex items-center justify-center" style={{ width: s, height: s }}>
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="absolute rounded-full"
          style={{
            width: s,
            height: s,
            border: `1px solid ${color}`,
            opacity: isRecording || isSpeaking ? 0.35 / i : 0.12 / i,
            transform: `scale(${1 + i * 0.18})`,
            animation: isRecording || isSpeaking
              ? `orb-ring-pulse ${1.2 + i * 0.3}s ease-in-out infinite alternate`
              : 'none',
            transition: 'all 0.4s ease',
          }}
        />
      ))}
      <div
        className="absolute rounded-full"
        style={{
          width: mid, height: mid,
          border: `2px solid ${color}`,
          opacity: 0.4,
          animation: isThinking ? 'orb-spin 2s linear infinite'
            : isRecording ? 'orb-spin 1s linear infinite' : 'none',
          transition: 'opacity 0.3s',
        }}
      />
      <div
        className="absolute rounded-full flex items-center justify-center"
        style={{
          width: core, height: core,
          background: `radial-gradient(circle at 38% 38%, ${color}44, ${color}11 70%)`,
          border: `2px solid ${color}88`,
          boxShadow: `0 0 ${isRecording || isSpeaking ? 36 : 14}px ${color}55`,
          transition: 'all 0.4s ease',
          animation: isRecording || isSpeaking
            ? 'orb-core-pulse 0.8s ease-in-out infinite alternate' : 'none',
        }}
      >
        <svg width={core * 0.7} height={core * 0.7} viewBox="0 0 80 80"
          style={{ opacity: 0.18, position: 'absolute' }}>
          <pattern id="hex2" x="0" y="0" width="20" height="17.32" patternUnits="userSpaceOnUse">
            <polygon points="10,0 20,5 20,15 10,20 0,15 0,5" fill="none" stroke={color} strokeWidth="0.5" />
          </pattern>
          <rect width="80" height="80" fill="url(#hex2)" />
        </svg>
        <div style={{ position: 'relative', zIndex: 1 }}>
          {isThinking
            ? <Loader2 size={core * 0.28} color={color} className="animate-spin" />
            : isRecording
            ? <StopCircle size={core * 0.28} color={color} />
            : <Bot size={core * 0.28} color={color} />}
        </div>
      </div>
      {(isThinking || isSpeaking) && (
        <svg className="absolute" width={s} height={s} viewBox={`0 0 ${s} ${s}`}
          style={{ animation: 'orb-spin 3s linear infinite' }}>
          <circle cx={s / 2} cy={s / 2} r={s * 0.455}
            fill="none" stroke={color} strokeWidth="2"
            strokeDasharray="60 460" strokeLinecap="round" opacity="0.6" />
        </svg>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Wave bars
// ---------------------------------------------------------------------------

function WaveBars({ active }: { active: boolean }) {
  const [bars, setBars] = useState<number[]>(Array(24).fill(3));
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (active) {
      ref.current = setInterval(() => {
        setBars(Array(24).fill(0).map(() => 3 + Math.random() * 26));
      }, 60);
    } else {
      if (ref.current) clearInterval(ref.current);
      setBars(Array(24).fill(3));
    }
    return () => { if (ref.current) clearInterval(ref.current); };
  }, [active]);
  return (
    <div className="flex items-end gap-[2px]" style={{ height: 28 }}>
      {bars.map((h, i) => (
        <div key={i} className="rounded-full transition-all duration-75" style={{
          width: 2.5, height: active ? h : 3,
          background: active ? 'var(--color-accent)' : 'var(--color-border)',
        }} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

const modeMeta = {
  plugin:  { label: 'Plugin',         color: 'var(--color-accent)' },
  control: { label: 'Desktop',        color: 'var(--color-accent-amber)' },
  qa:      { label: 'AI',             color: 'var(--color-accent-purple)' },
} as const;

function Bubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mr-2 mt-0.5"
          style={{ background: 'var(--color-accent-subtle)', border: '1px solid var(--color-accent)44' }}>
          <Bot size={14} style={{ color: 'var(--color-accent)' }} />
        </div>
      )}
      <div style={{ maxWidth: '72%' }}>
        {!isUser && msg.mode && (
          <div className="flex items-center gap-1.5 mb-1">
            {msg.mode === 'control' && <Zap size={10} style={{ color: modeMeta.control.color }} />}
            <span className="text-[10px] font-semibold uppercase tracking-widest"
              style={{ color: modeMeta[msg.mode].color }}>
              {modeMeta[msg.mode].label}
            </span>
          </div>
        )}
        <div
          className="rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap"
          style={{
            background: isUser ? 'var(--color-user-bubble)' : 'var(--color-bg-secondary)',
            color: isUser ? 'var(--color-user-bubble-text)' : 'var(--color-text)',
            border: isUser ? 'none' : '1px solid var(--color-border)',
            borderBottomRightRadius: isUser ? 4 : undefined,
            borderBottomLeftRadius: !isUser ? 4 : undefined,
          }}
        >
          {msg.content}
        </div>
        <div className="flex items-center gap-2 mt-1 px-1">
          <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
            {new Date(msg.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          {!isUser && (msg.promptTokens ?? 0) > 0 && (
            <span
              className="text-[10px] px-1.5 py-0.5 rounded font-mono"
              style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}
              title={`${msg.promptTokens} prompt + ${msg.completionTokens} completion tokens`}
            >
              {msg.promptTokens}↑ {msg.completionTokens}↓
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status bar
// ---------------------------------------------------------------------------

function StatusBar({ online }: { online: boolean }) {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="flex items-center justify-between px-4 py-2 shrink-0"
      style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ background: online ? '#22c55e' : '#ef4444',
          boxShadow: online ? '0 0 6px #22c55e88' : 'none' }} />
        <span className="text-xs font-semibold" style={{
          color: 'var(--color-text-secondary)', fontFamily: 'var(--font-hud)', letterSpacing: '0.1em' }}>
          {online ? 'JARVIS ONLINE' : 'CONNECTING…'}
        </span>
      </div>
      <div className="flex items-center gap-3">
        {online ? <Wifi size={12} style={{ color: 'var(--color-text-tertiary)' }} />
                : <WifiOff size={12} style={{ color: 'var(--color-error)' }} />}
        <span className="text-xs" style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-hud)' }}>
          <Clock size={10} className="inline mr-1" />
          {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main JarvisPage
// ---------------------------------------------------------------------------

export function JarvisPage() {
  const [phase, setPhase]       = useState<Phase>('idle');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput]       = useState('');
  const [countdown, setCountdown] = useState(RECORD_SECONDS);
  const [error, setError]       = useState('');
  const [ttsOn, setTtsOn]       = useState(true);
  const [voice, setVoice]       = useState('hannah');
  const [online, setOnline]     = useState(false);
  const [voiceMode, setVoiceMode] = useState<VoiceMode>('push-to-talk');

  const mediaRef  = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef  = useRef<HTMLAudioElement | null>(null);
  const feedRef   = useRef<HTMLDivElement>(null);
  const speechRef = useRef<SpeechRecognition | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const deepgramWsRef = useRef<WebSocket | null>(null);
  const deepgramAudioContextRef = useRef<AudioContext | null>(null);

  // Auto-scroll feed
  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  // Health check
  useEffect(() => {
    const check = () =>
      fetch(`${getBase()}/api/jarvis/health`)
        .then((r) => setOnline(r.ok))
        .catch(() => setOnline(false));
    check();
    const t = setInterval(check, 10_000);
    return () => clearInterval(t);
  }, []);

  const pushMsg = (
    role: 'user' | 'jarvis',
    content: string,
    mode?: Message['mode'],
    promptTokens?: number,
    completionTokens?: number,
  ) =>
    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString(36) + Math.random(), role, content, mode, ts: Date.now(), promptTokens, completionTokens },
    ]);

  // ── Play TTS ──────────────────────────────────────────────────────────────

  const playAudio = useCallback((b64: string) => {
    try {
      const binary = atob(b64);
      const bytes  = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: 'audio/wav' });
      const url  = URL.createObjectURL(blob);
      if (audioRef.current) { audioRef.current.pause(); URL.revokeObjectURL(audioRef.current.src); }
      const audio = new Audio(url);
      audioRef.current = audio;
      setPhase('speaking');
      audio.onended = () => { setPhase('done'); URL.revokeObjectURL(url); };
      audio.onerror = () => setPhase('done');
      audio.play().catch(() => setPhase('done'));
    } catch { setPhase('done'); }
  }, []);

  // ── Text chat ─────────────────────────────────────────────────────────────

  const sendText = useCallback(async (text: string) => {
    if (!text.trim()) return;
    pushMsg('user', text);
    setInput('');
    setPhase('thinking');
    try {
      const res = await fetch(`${getBase()}/api/jarvis/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, tts: ttsOn, voice }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(d.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      pushMsg('jarvis', data.response, data.mode, data.prompt_tokens, data.completion_tokens);
      if (ttsOn && data.audio_b64) {
        playAudio(data.audio_b64);
      } else {
        setPhase('done');
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      pushMsg('jarvis', `Error: ${msg}`, 'qa');
      setPhase('error');
    }
  }, [ttsOn, voice, playAudio]);

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(input); }
  };

  // ── Voice recording ───────────────────────────────────────────────────────

  const stopRecording = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    mediaRef.current?.stop();
  }, []);

  const startRecording = useCallback(async () => {
    setError('');
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
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
      setPhase('transcribing');
      try {
        const fd = new FormData();
        fd.append('audio', blob, 'recording.webm');
        const res = await fetch(`${getBase()}/api/jarvis/voice?tts=${ttsOn}&voice=${voice}`, {
          method: 'POST', body: fd,
        });
        if (!res.ok) {
          const d = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(d.detail || `Error ${res.status}`);
        }
        const data = await res.json();
        if (data.transcript) pushMsg('user', data.transcript);
        if (data.response)   pushMsg('jarvis', data.response, data.mode);
        setPhase('thinking');
        if (ttsOn && data.audio_b64) {
          playAudio(data.audio_b64);
        } else {
          setPhase('done');
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        pushMsg('jarvis', `Error: ${msg}`, 'qa');
        setPhase('error');
      }
    };
    recorder.start();
    let remaining = RECORD_SECONDS;
    timerRef.current = setInterval(() => {
      remaining -= 1;
      setCountdown(remaining);
      if (remaining <= 0) { clearInterval(timerRef.current!); stopRecording(); }
    }, 1000);
  }, [stopRecording, ttsOn, voice, playAudio]);

  const handleMicClick = () => {
    if (phase === 'recording') { stopRecording(); return; }
    if (phase === 'speaking')  { audioRef.current?.pause(); setPhase('done'); return; }
    if (['idle', 'done', 'error'].includes(phase)) startRecording();
  };

  // ── Always-on voice mode using Web Speech API ─────────────────────────────

  const startAlwaysOnVoice = useCallback(() => {
    if (!('SpeechRecognition' in window) && !('webkitSpeechRecognition' in window)) {
      setError('Speech recognition not supported in this browser.');
      setPhase('error');
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    let finalTranscript = '';
    let silenceTimeout: ReturnType<typeof setTimeout> | null = null;

    recognition.onresult = (event: any) => {
      let interimTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
          // Reset silence timer on final result
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = setTimeout(() => {
            if (finalTranscript.trim()) {
              sendText(finalTranscript.trim());
              finalTranscript = '';
            }
          }, 1200); // Send after 1.2s of silence
        } else {
          interimTranscript += transcript;
        }
      }
    };

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
      if (event.error === 'no-speech') {
        // Restart on no-speech error
        recognition.start();
      } else {
        setError(`Speech recognition error: ${event.error}`);
        setPhase('error');
        setVoiceMode('push-to-talk');
      }
    };

    recognition.onend = () => {
      if (voiceMode === 'always-on') {
        // Restart if still in always-on mode
        try {
          recognition.start();
        } catch (e) {
          // Already started
        }
      }
    };

    speechRef.current = recognition;
    try {
      recognition.start();
      setPhase('recording');
    } catch (e) {
      console.error('Failed to start speech recognition:', e);
    }
  }, [voiceMode, sendText]);

  const stopAlwaysOnVoice = useCallback(() => {
    if (speechRef.current) {
      speechRef.current.stop();
      speechRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    setPhase('idle');
  }, []);

  useEffect(() => {
    if (voiceMode === 'always-on') {
      startAlwaysOnVoice();
    } else {
      stopAlwaysOnVoice();
    }
    return () => {
      stopAlwaysOnVoice();
    };
  }, [voiceMode, startAlwaysOnVoice, stopAlwaysOnVoice]);

  // ── Deepgram WebSocket connection ───────────────────────────────────────────

  const startDeepgramConnection = useCallback(async () => {
    try {
      const ws = new WebSocket(`${getBase().replace('http', 'ws')}/api/deepgram/ws`);
      deepgramWsRef.current = ws;

      ws.onopen = () => {
        console.log('Deepgram WebSocket connected');
        setPhase('recording');
        setError('');
      };

      ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          // Handle Deepgram responses
          if (data.type === 'user_speech') {
            pushMsg('user', data.content);
          } else if (data.type === 'agent_response') {
            pushMsg('jarvis', data.content);
            if (data.audio) {
              playAudio(data.audio);
            }
          }
        } catch (e) {
          // Binary data (audio)
          if (event.data instanceof Blob) {
            // Handle audio blob
            const arrayBuffer = await event.data.arrayBuffer();
            const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
            playAudio(base64);
          }
        }
      };

      ws.onerror = (error) => {
        console.error('Deepgram WebSocket error:', error);
        setError('Deepgram connection error');
        setPhase('error');
      };

      ws.onclose = () => {
        console.log('Deepgram WebSocket closed');
        if (voiceMode === 'deepgram') {
          setPhase('idle');
        }
      };
    } catch (e) {
      console.error('Failed to connect to Deepgram:', e);
      setError('Failed to connect to Deepgram');
      setPhase('error');
    }
  }, [voiceMode, playAudio]);

  const stopDeepgramConnection = useCallback(() => {
    if (deepgramWsRef.current) {
      deepgramWsRef.current.close();
      deepgramWsRef.current = null;
    }
    if (deepgramAudioContextRef.current) {
      deepgramAudioContextRef.current.close();
      deepgramAudioContextRef.current = null;
    }
    setPhase('idle');
  }, []);

  useEffect(() => {
    if (voiceMode === 'deepgram') {
      startDeepgramConnection();
    } else {
      stopDeepgramConnection();
    }
    return () => {
      stopDeepgramConnection();
    };
  }, [voiceMode, startDeepgramConnection, stopDeepgramConnection]);

  const isRecording = phase === 'recording';
  const isWorking   = phase === 'transcribing' || phase === 'thinking';

  const phaseLabel: Record<Phase, string> = {
    idle:         voiceMode === 'always-on' ? 'Always-ON listening — just speak' : voiceMode === 'deepgram' ? 'Deepgram connected — speak naturally' : 'Ready — click the orb or type a command',
    recording:    voiceMode === 'always-on' ? 'Always-ON listening…' : voiceMode === 'deepgram' ? 'Deepgram listening…' : `Listening… ${countdown}s`,
    transcribing: 'Transcribing your voice…',
    thinking:     'Processing command…',
    speaking:     'Jarvis is speaking…',
    done:         voiceMode === 'always-on' ? 'Always-ON listening — just speak' : voiceMode === 'deepgram' ? 'Deepgram connected — speak naturally' : 'Ready',
    error:        error || 'Error',
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <StatusBar online={online} />

      <div className="flex flex-1 overflow-hidden">
        {/* ── Left: orb + chat feed ── */}
        <div className="flex flex-col flex-1 overflow-hidden">

          {/* Orb area */}
          <div className="flex flex-col items-center justify-center gap-4 py-6 shrink-0"
            style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)' }}>
            <button
              onClick={voiceMode !== 'push-to-talk' ? undefined : handleMicClick}
              disabled={isWorking || voiceMode !== 'push-to-talk'}
              className="transition-transform duration-150 focus:outline-none"
              style={{ cursor: (isWorking || voiceMode !== 'push-to-talk') ? 'default' : 'pointer', opacity: (isWorking || voiceMode !== 'push-to-talk') ? 0.85 : 1 }}
              aria-label={voiceMode === 'always-on' ? 'Always-on listening' : voiceMode === 'deepgram' ? 'Deepgram listening' : isRecording ? 'Stop' : 'Start voice'}
            >
              <JarvisOrb phase={phase} size={140} />
            </button>

            <WaveBars active={isRecording} />

            <p className="text-xs font-medium tracking-wide text-center px-4"
              style={{ color: phase === 'error' ? 'var(--color-error)' : 'var(--color-text-secondary)' }}>
              {phaseLabel[phase]}
            </p>
          </div>

          {/* Chat feed */}
          <div ref={feedRef} className="flex-1 overflow-y-auto px-4 py-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40">
                <Bot size={40} style={{ color: 'var(--color-text-tertiary)' }} />
                <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
                  Click the orb to speak, or type below
                </p>
              </div>
            ) : (
              messages.map((m) => <Bubble key={m.id} msg={m} />)
            )}
          </div>

          {/* Input bar */}
          <div className="shrink-0 px-4 pb-4 pt-2" style={{ borderTop: '1px solid var(--color-border)' }}>
            <div className="flex items-center gap-2 rounded-xl px-3 py-2"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>

              {/* Mic */}
              <button
                onClick={voiceMode !== 'push-to-talk' ? undefined : handleMicClick}
                disabled={isWorking || voiceMode !== 'push-to-talk'}
                className="rounded-full p-1.5 flex items-center justify-center transition-colors shrink-0 cursor-pointer"
                style={{
                  background: isRecording ? 'var(--color-error)' : 'transparent',
                  color: isRecording ? '#fff' : 'var(--color-text-secondary)',
                  opacity: voiceMode !== 'push-to-talk' ? 0.4 : 1,
                }}
                title={voiceMode === 'always-on' ? 'Always-ON mode active' : voiceMode === 'deepgram' ? 'Deepgram mode active' : isRecording ? 'Stop recording' : 'Start recording'}
              >
                {voiceMode !== 'push-to-talk' ? <Mic size={16} /> : isRecording ? <StopCircle size={16} /> : <Mic size={16} />}
              </button>

              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Ask Jarvis anything or give a command…"
                disabled={isWorking || isRecording}
                className="flex-1 bg-transparent outline-none text-sm"
                style={{ color: 'var(--color-text)' }}
              />

              {/* TTS toggle */}
              <button
                onClick={() => setTtsOn((v) => !v)}
                className="p-1.5 rounded-full transition-colors cursor-pointer shrink-0"
                style={{ color: ttsOn ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}
                title={ttsOn ? 'Disable voice' : 'Enable voice'}
              >
                {ttsOn ? <Volume2 size={15} /> : <VolumeX size={15} />}
              </button>

              {/* Send */}
              <button
                onClick={() => sendText(input)}
                disabled={!input.trim() || isWorking}
                className="rounded-lg p-1.5 transition-colors cursor-pointer shrink-0"
                style={{
                  background: input.trim() && !isWorking ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                  color: input.trim() && !isWorking ? '#fff' : 'var(--color-text-tertiary)',
                }}
              >
                {isWorking ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              </button>
            </div>
          </div>
        </div>

        {/* ── Right: quick commands + voice settings ── */}
        <div className="w-64 shrink-0 flex flex-col overflow-hidden"
          style={{ borderLeft: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}>

          {/* Voice settings */}
          <div className="px-4 py-3 shrink-0" style={{ borderBottom: '1px solid var(--color-border)' }}>
            <p className="text-xs font-semibold uppercase tracking-widest mb-2"
              style={{ color: 'var(--color-text-tertiary)' }}>Voice Mode</p>
            <div className="flex flex-col gap-2 mb-2">
              <button
                onClick={() => setVoiceMode('push-to-talk')}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors cursor-pointer text-left"
                style={{
                  background: voiceMode === 'push-to-talk' ? 'var(--color-accent-subtle)' : 'var(--color-bg-tertiary)',
                  border: `1px solid ${voiceMode === 'push-to-talk' ? 'var(--color-accent)' : 'var(--color-border)'}`,
                  color: voiceMode === 'push-to-talk' ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                }}
              >
                <MicOff size={11} />
                Push-to-Talk
              </button>
              <button
                onClick={() => setVoiceMode('always-on')}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors cursor-pointer text-left"
                style={{
                  background: voiceMode === 'always-on' ? 'var(--color-accent-subtle)' : 'var(--color-bg-tertiary)',
                  border: `1px solid ${voiceMode === 'always-on' ? 'var(--color-accent)' : 'var(--color-border)'}`,
                  color: voiceMode === 'always-on' ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                }}
              >
                <Mic size={11} />
                Always-ON (Web Speech)
              </button>
              <button
                onClick={() => setVoiceMode('deepgram')}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors cursor-pointer text-left"
                style={{
                  background: voiceMode === 'deepgram' ? 'var(--color-accent-subtle)' : 'var(--color-bg-tertiary)',
                  border: `1px solid ${voiceMode === 'deepgram' ? 'var(--color-accent)' : 'var(--color-border)'}`,
                  color: voiceMode === 'deepgram' ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                }}
              >
                <Bot size={11} />
                Deepgram Agent
              </button>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setTtsOn((v) => !v)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition-colors cursor-pointer"
                style={{
                  background: ttsOn ? 'var(--color-accent-subtle)' : 'var(--color-bg-tertiary)',
                  border: `1px solid ${ttsOn ? 'var(--color-accent)' : 'var(--color-border)'}`,
                  color: ttsOn ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                }}
              >
                {ttsOn ? <Volume2 size={11} /> : <VolumeX size={11} />}
                {ttsOn ? 'Speak ON' : 'Speak OFF'}
              </button>
            </div>
            {ttsOn && (
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="w-full text-xs px-2 py-1.5 rounded-lg outline-none cursor-pointer"
                style={{
                  background: 'var(--color-bg-tertiary)',
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

          {/* Quick commands */}
          <div className="flex-1 overflow-y-auto px-3 py-3">
            <p className="text-xs font-semibold uppercase tracking-widest mb-2 px-1"
              style={{ color: 'var(--color-text-tertiary)' }}>Quick Commands</p>
            <div className="flex flex-col gap-1">
              {QUICK_COMMANDS.map(({ label, cmd }) => (
                <button
                  key={label}
                  onClick={() => sendText(cmd)}
                  disabled={isWorking || isRecording}
                  className="flex items-center justify-between text-xs px-3 py-2 rounded-lg text-left transition-colors cursor-pointer"
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text-secondary)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-surface)')}
                >
                  <span>{label}</span>
                  <ChevronRight size={10} style={{ color: 'var(--color-text-tertiary)' }} />
                </button>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="px-4 py-3 shrink-0" style={{ borderTop: '1px solid var(--color-border)' }}>
            <p className="text-[10px] text-center" style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-hud)' }}>
              OpenJarvis v3 · Groq · Whisper · Orpheus
            </p>
          </div>
        </div>
      </div>

      {/* CSS keyframes */}
      <style>{`
        @keyframes orb-ring-pulse {
          from { opacity: 0.06; transform: scale(1.18); }
          to   { opacity: 0.28; transform: scale(1.28); }
        }
        @keyframes orb-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes orb-core-pulse {
          from { box-shadow: 0 0 16px var(--color-accent)44; }
          to   { box-shadow: 0 0 40px var(--color-accent)88; }
        }
      `}</style>
    </div>
  );
}
