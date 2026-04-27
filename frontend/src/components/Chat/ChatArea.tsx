import { useRef, useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { MessageBubble } from './MessageBubble';
import { InputArea } from './InputArea';
import { StreamingDots } from './StreamingDots';
import { useAppStore } from '../../lib/store';
import { Sparkles, PanelRightOpen, PanelRightClose, Database, MessageSquare, X, Volume2, VolumeX } from 'lucide-react';
import { listConnectors } from '../../lib/connectors-api';
import { getBase } from '../../lib/api';

const TTS_VOICE = 'hannah';
const TTS_STORAGE_KEY = 'openjarvis-chat-tts-on';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export function ChatArea() {
  const messages = useAppStore((s) => s.messages);
  const streamState = useAppStore((s) => s.streamState);
  const systemPanelOpen = useAppStore((s) => s.systemPanelOpen);
  const toggleSystemPanel = useAppStore((s) => s.toggleSystemPanel);
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);

  // TTS state
  const [ttsOn, setTtsOn] = useState(() => {
    try { return localStorage.getItem(TTS_STORAGE_KEY) !== 'false'; } catch { return true; }
  });
  const [ttsAvailable, setTtsAvailable] = useState<boolean | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const prevStreamingRef = useRef(false);
  const lastSpokenIdRef = useRef<string>('');

  // Check if Jarvis TTS backend is available on mount
  useEffect(() => {
    fetch(`${getBase()}/api/jarvis/health`)
      .then((r) => r.json())
      .then((d) => setTtsAvailable(!!d.tts_available && !!d.groq_key_set))
      .catch(() => setTtsAvailable(false));
  }, []);

  const toggleTts = useCallback(() => {
    setTtsOn((v) => {
      const next = !v;
      try { localStorage.setItem(TTS_STORAGE_KEY, String(next)); } catch {}
      if (!next && audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
      return next;
    });
  }, []);

  const speakText = useCallback(async (text: string) => {
    if (!text.trim()) return;
    // Strip markdown symbols for cleaner speech
    const clean = text.replace(/[#*`_~\[\]()]/g, '').replace(/\n+/g, ' ').trim();
    // Truncate to 400 chars so TTS stays snappy
    const snippet = clean.length > 400 ? clean.slice(0, 400) + '...' : clean;
    try {
      const res = await fetch(`${getBase()}/api/jarvis/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: snippet, voice: TTS_VOICE }),
      });
      if (!res.ok) {
        console.warn(`[TTS] Request failed: HTTP ${res.status} ${res.statusText}`);
        return;
      }
      // Endpoint returns raw audio/wav bytes
      const blob = await res.blob();
      if (!blob.size) {
        console.warn('[TTS] Received empty audio blob');
        return;
      }
      const url = URL.createObjectURL(blob);
      if (audioRef.current) { audioRef.current.pause(); URL.revokeObjectURL(audioRef.current.src); }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => URL.revokeObjectURL(url);
      audio.play().catch((err) => console.warn('[TTS] Playback failed:', err));
    } catch (err) {
      console.warn('[TTS] Error:', err);
    }
  }, []);

  // Auto-speak when streaming finishes
  useEffect(() => {
    const wasStreaming = prevStreamingRef.current;
    const isStreaming = streamState.isStreaming;
    prevStreamingRef.current = isStreaming;

    if (wasStreaming && !isStreaming && ttsOn && ttsAvailable) {
      // Find the last assistant message
      const last = [...messages].reverse().find((m) => m.role === 'assistant');
      if (last && last.id !== lastSpokenIdRef.current && last.content) {
        lastSpokenIdRef.current = last.id;
        speakText(last.content);
      }
    }
  }, [streamState.isStreaming, messages, ttsOn, ttsAvailable, speakText]);

  // Check if any data sources are connected
  const [hasConnectedSources, setHasConnectedSources] = useState<boolean | null>(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  useEffect(() => {
    listConnectors()
      .then((list) => setHasConnectedSources(list.some((c) => c.connected)))
      .catch(() => setHasConnectedSources(null));
  }, []);

  useEffect(() => {
    if (shouldAutoScroll.current && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, streamState.content]);

  const handleScroll = () => {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    shouldAutoScroll.current = scrollHeight - scrollTop - clientHeight < 100;
  };

  const isEmpty = messages.length === 0 && !streamState.isStreaming;

  const PanelIcon = systemPanelOpen ? PanelRightClose : PanelRightOpen;

  return (
    <div className="flex flex-col h-full">
      {/* Toggle bar */}
      <div className="flex items-center justify-end gap-1 px-3 py-1.5 shrink-0">
        {/* TTS toggle */}
        <button
          onClick={ttsAvailable === false ? undefined : toggleTts}
          className="p-1.5 rounded-md transition-colors cursor-pointer"
          style={{
            color: ttsAvailable === false
              ? 'var(--color-text-tertiary)'
              : ttsOn ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
            opacity: ttsAvailable === false ? 0.4 : 1,
            cursor: ttsAvailable === false ? 'not-allowed' : 'pointer',
          }}
          title={
            ttsAvailable === false
              ? 'Voice unavailable — GROQ_API_KEY not configured'
              : ttsOn ? 'Voice ON — click to mute' : 'Voice OFF — click to enable'
          }
        >
          {ttsOn && ttsAvailable !== false ? <Volume2 size={15} /> : <VolumeX size={15} />}
        </button>
        <button
          onClick={toggleSystemPanel}
          className="p-1.5 rounded-md transition-colors cursor-pointer"
          style={{ color: 'var(--color-text-tertiary)' }}
          title={`${systemPanelOpen ? 'Hide' : 'Show'} system panel (${navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+I)`}
        >
          <PanelIcon size={16} />
        </button>
      </div>

      {/* Data sources banner */}
      {hasConnectedSources === false && !bannerDismissed && (
        <div
          className="mx-4 mb-2 flex items-center gap-3 px-4 py-3 rounded-lg text-sm shrink-0"
          style={{
            background: 'var(--color-accent-subtle)',
            border: '1px solid var(--color-border)',
          }}
        >
          <Database size={16} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
          <span style={{ color: 'var(--color-text-secondary)', flex: 1 }}>
            Connect your data sources (Gmail, iMessage, Slack, etc.) to get personalized answers.
          </span>
          <button
            onClick={() => navigate('/data-sources')}
            className="px-3 py-1 rounded text-xs font-medium cursor-pointer"
            style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)', border: 'none' }}
          >
            Connect
          </button>
          <button
            onClick={() => setBannerDismissed(true)}
            className="p-1 rounded cursor-pointer"
            style={{ color: 'var(--color-text-tertiary)', background: 'transparent', border: 'none' }}
          >
            <X size={14} />
          </button>
        </div>
      )}
      <div
        ref={listRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full px-4">
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}
            >
              <Sparkles size={24} />
            </div>
            <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
              {getGreeting()}
            </h2>
            <p className="text-sm text-center max-w-sm mb-6" style={{ color: 'var(--color-text-secondary)' }}>
              Ask anything. Your AI runs locally — private, fast, and always available.
            </p>

            {/* Quick action hints */}
            <div className="flex gap-3">
              <button
                onClick={() => navigate('/data-sources')}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs cursor-pointer transition-colors"
                style={{
                  background: 'var(--color-bg-secondary)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-secondary)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-accent)')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-border)')}
              >
                <Database size={14} style={{ color: 'var(--color-accent)' }} />
                Connect Data Sources
              </button>
              <button
                onClick={() => { navigate('/data-sources'); setTimeout(() => window.dispatchEvent(new CustomEvent('switch-tab', { detail: 'messaging' })), 100); }}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs cursor-pointer transition-colors"
                style={{
                  background: 'var(--color-bg-secondary)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-secondary)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-accent)')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-border)')}
              >
                <MessageSquare size={14} style={{ color: 'var(--color-accent)' }} />
                Set Up Messaging Channels
              </button>
            </div>
          </div>
        ) : (
          <div className="max-w-[var(--chat-max-width)] mx-auto px-4 py-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {streamState.isStreaming && streamState.content === '' && (
              <div className="flex justify-start mb-4">
                <StreamingDots phase={streamState.phase} />
              </div>
            )}
          </div>
        )}
      </div>
      <InputArea />
    </div>
  );
}
