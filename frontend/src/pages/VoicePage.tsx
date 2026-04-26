import { useState, useRef, useEffect, useCallback } from 'react';
import { Mic, MicOff, Volume2, Loader2, Zap, StopCircle } from 'lucide-react';
import { runVoiceCommand } from '../lib/api';

type Phase = 'idle' | 'recording' | 'transcribing' | 'thinking' | 'speaking' | 'done' | 'error';

interface HistoryItem {
  id: string;
  you: string;
  jarvis: string;
  mode: 'qa' | 'control';
  ts: number;
}

const RECORD_SECONDS = 6;

function WaveBar({ active, index }: { active: boolean; index: number }) {
  return (
    <div
      className="rounded-full transition-all"
      style={{
        width: 3,
        background: active ? 'var(--color-accent)' : 'var(--color-border)',
        height: active ? `${16 + Math.sin(Date.now() / 200 + index) * 12}px` : '6px',
        animation: active ? `wave-bar ${0.6 + index * 0.08}s ease-in-out infinite alternate` : 'none',
        animationDelay: `${index * 60}ms`,
      }}
    />
  );
}

export function VoicePage() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [countdown, setCountdown] = useState(RECORD_SECONDS);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [mode, setMode] = useState<'qa' | 'control'>('qa');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState('');
  const [bars, setBars] = useState<number[]>(Array(20).fill(6));

  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const animRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Animate waveform bars when recording
  useEffect(() => {
    if (phase === 'recording') {
      animRef.current = setInterval(() => {
        setBars(Array(20).fill(0).map(() => 6 + Math.random() * 24));
      }, 80);
    } else {
      if (animRef.current) clearInterval(animRef.current);
      setBars(Array(20).fill(6));
    }
    return () => { if (animRef.current) clearInterval(animRef.current); };
  }, [phase]);

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
        const result = await runVoiceCommand(blob);
        setTranscript(result.transcript || '');
        setMode(result.mode || 'qa');
        setPhase('thinking');
        setResponse(result.response || '');
        setPhase('done');
        setHistory((h) => [
          {
            id: Date.now().toString(36),
            you: result.transcript || '',
            jarvis: result.response || '',
            mode: result.mode || 'qa',
            ts: Date.now(),
          },
          ...h.slice(0, 49),
        ]);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        setPhase('error');
      }
    };

    recorder.start();

    // Countdown
    let remaining = RECORD_SECONDS;
    timerRef.current = setInterval(() => {
      remaining -= 1;
      setCountdown(remaining);
      if (remaining <= 0) {
        clearInterval(timerRef.current!);
        stopRecording();
      }
    }, 1000);
  }, [stopRecording]);

  const handleMicClick = () => {
    if (phase === 'recording') {
      stopRecording();
    } else if (phase === 'idle' || phase === 'done' || phase === 'error') {
      startRecording();
    }
  };

  const isRecording = phase === 'recording';
  const isWorking = phase === 'transcribing' || phase === 'thinking';

  const phaseLabel: Record<Phase, string> = {
    idle: 'Press the mic to speak',
    recording: `Recording… ${countdown}s`,
    transcribing: 'Transcribing…',
    thinking: 'Jarvis is thinking…',
    speaking: 'Speaking…',
    done: 'Done — press mic to speak again',
    error: error || 'Error',
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main panel */}
      <div className="flex-1 flex flex-col items-center justify-start overflow-y-auto px-6 py-10">
        <div className="w-full max-w-xl">
          {/* Header */}
          <div className="mb-8 text-center">
            <h1 className="text-2xl font-semibold mb-1" style={{ color: 'var(--color-text)' }}>
              Voice Mode
            </h1>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Speak a question or give Jarvis a command to control your machine
            </p>
          </div>

          {/* Mic button + waveform */}
          <div className="flex flex-col items-center gap-6 mb-8">
            {/* Waveform */}
            <div className="flex items-end gap-[3px] h-10">
              {bars.map((h, i) => (
                <div
                  key={i}
                  className="rounded-full transition-all duration-75"
                  style={{
                    width: 3,
                    height: isRecording ? h : 6,
                    background: isRecording ? 'var(--color-accent)' : 'var(--color-border)',
                  }}
                />
              ))}
            </div>

            {/* Mic button */}
            <button
              onClick={handleMicClick}
              disabled={isWorking}
              className="relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer"
              style={{
                background: isRecording
                  ? 'var(--color-error)'
                  : isWorking
                    ? 'var(--color-bg-tertiary)'
                    : 'var(--color-accent)',
                boxShadow: isRecording
                  ? '0 0 0 8px rgba(220,38,38,0.15), 0 0 0 16px rgba(220,38,38,0.07)'
                  : isWorking
                    ? 'none'
                    : '0 0 0 8px var(--color-accent-subtle)',
                opacity: isWorking ? 0.5 : 1,
                cursor: isWorking ? 'default' : 'pointer',
              }}
            >
              {isWorking ? (
                <Loader2 size={28} className="animate-spin text-white" />
              ) : isRecording ? (
                <StopCircle size={28} color="white" />
              ) : (
                <Mic size={28} color="white" />
              )}
            </button>

            {/* Phase label */}
            <p className="text-sm font-medium" style={{ color: phase === 'error' ? 'var(--color-error)' : 'var(--color-text-secondary)' }}>
              {phaseLabel[phase]}
            </p>
          </div>

          {/* Transcript + response */}
          {(transcript || response) && (
            <div className="flex flex-col gap-3 mb-6">
              {transcript && (
                <div
                  className="rounded-xl px-4 py-3"
                  style={{ background: 'var(--color-accent-subtle)', border: '1px solid var(--color-accent-subtle)' }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Mic size={12} style={{ color: 'var(--color-accent)' }} />
                    <span className="text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--color-accent)' }}>You</span>
                    {mode === 'control' && (
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                        style={{ background: 'var(--color-accent-amber-subtle)', color: 'var(--color-accent-amber)' }}
                      >
                        <Zap size={8} className="inline mr-0.5" />Desktop Control
                      </span>
                    )}
                  </div>
                  <p className="text-sm" style={{ color: 'var(--color-text)' }}>{transcript}</p>
                </div>
              )}

              {response && (
                <div
                  className="rounded-xl px-4 py-3"
                  style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Volume2 size={12} style={{ color: 'var(--color-text-secondary)' }} />
                    <span className="text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-secondary)' }}>Jarvis</span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--color-text)' }}>{response}</p>
                </div>
              )}
            </div>
          )}

          {/* Quick commands */}
          <div className="mb-6">
            <p className="text-xs font-medium mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Example commands
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                'Open Chrome', 'Search for the weather', 'Close Notepad',
                'Take a screenshot', 'What is the capital of France?',
                'Show desktop', 'Volume up',
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

      {/* History sidebar */}
      {history.length > 0 && (
        <div
          className="w-72 shrink-0 flex flex-col overflow-hidden"
          style={{ borderLeft: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
        >
          <div className="px-4 py-3 shrink-0" style={{ borderBottom: '1px solid var(--color-border)' }}>
            <h2 className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>History</h2>
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
                  ) : (
                    <Volume2 size={10} style={{ color: 'var(--color-accent)' }} />
                  )}
                  <span className="font-medium truncate" style={{ color: 'var(--color-text)' }}>{item.you}</span>
                </div>
                <p className="line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>{item.jarvis}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
