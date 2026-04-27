/**
 * OpenJarvis — Channels & Messaging Hub
 *
 * Lets you:
 *  1. Chat directly via built-in WebChat (no setup needed)
 *  2. Connect external channels (Telegram, Discord, Slack, …)
 *     and have Jarvis auto-reply to incoming messages
 *
 * Architecture:
 *  - Left panel: channel list with connect/disconnect buttons
 *  - Right panel: either a WebChat window OR a setup guide for the selected channel
 */

import { useState, useEffect, useRef, useCallback, KeyboardEvent } from 'react';
import {
  MessageSquare, Send, Loader2, Wifi, WifiOff,
  Trash2, CheckCircle, XCircle, ExternalLink,
  ChevronRight, Bot, User, RefreshCw, Info, QrCode,
} from 'lucide-react';
import { getBase } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChannelField {
  key: string;
  label: string;
  placeholder: string;
}

interface ChannelMeta {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: 'connected' | 'disconnected' | 'connecting' | 'error' | 'unknown';
  easy: boolean;
  fields: ChannelField[];
  setup_steps: string[];
  setup_url: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function fetchChannels(base: string): Promise<ChannelMeta[]> {
  const r = await fetch(`${base}/api/channels`);
  if (!r.ok) return [];
  const d = await r.json();
  return d.channels ?? [];
}

async function connectChannel(
  base: string,
  channelId: string,
  creds: Record<string, string>,
): Promise<{ ok: boolean; status: string; error?: string }> {
  const r = await fetch(`${base}/api/channels/${channelId}/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds),
  });
  const d = await r.json();
  if (!r.ok) return { ok: false, status: 'error', error: d.detail ?? r.statusText };
  return { ok: d.ok, status: d.status };
}

async function disconnectChannel(base: string, channelId: string) {
  await fetch(`${base}/api/channels/${channelId}/disconnect`, { method: 'POST' });
}

async function sendWebchat(
  base: string,
  text: string,
  convId: string,
): Promise<{ reply: string; history: ChatMessage[] }> {
  const r = await fetch(`${base}/api/channels/webchat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, conversation_id: convId }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? r.statusText);
  }
  return r.json();
}

// ---------------------------------------------------------------------------
// Colour for status badge
// ---------------------------------------------------------------------------

function statusColor(s: string) {
  if (s === 'connected') return '#22c55e';
  if (s === 'connecting') return '#f59e0b';
  if (s === 'error') return '#ef4444';
  return '#475569';
}

function StatusDot({ status }: { status: string }) {
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: statusColor(status),
      boxShadow: status === 'connected' ? `0 0 6px ${statusColor(status)}` : 'none',
    }} />
  );
}

// ---------------------------------------------------------------------------
// WebChat component (right panel when webchat is selected)
// ---------------------------------------------------------------------------

function WebChatPanel({ base }: { base: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const convId = useRef('jarvis-' + Date.now());
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setError(null);
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);
    try {
      const res = await sendWebchat(base, text, convId.current);
      setMessages(res.history);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, base]);

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const clear = () => {
    setMessages([]);
    convId.current = 'jarvis-' + Date.now();
    fetch(`${base}/api/channels/webchat/history/${convId.current}`, { method: 'DELETE' });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 20px', borderBottom: '1px solid rgba(0,200,255,0.1)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20 }}>💬</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#e2e8f0' }}>Web Chat</div>
            <div style={{ fontSize: 11, color: '#64748b' }}>Powered by OpenJarvis — no setup needed</div>
          </div>
        </div>
        <button onClick={clear} title="Clear conversation" style={{
          background: 'none', border: 'none', cursor: 'pointer', color: '#475569', padding: 6,
        }}>
          <Trash2 size={15} />
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#334155', padding: '40px 20px' }}>
            <Bot size={40} style={{ marginBottom: 12, opacity: 0.4 }} />
            <div style={{ fontSize: 14, marginBottom: 6 }}>Chat with Jarvis</div>
            <div style={{ fontSize: 12, color: '#1e293b' }}>
              Ask anything — time, weather, news, Wikipedia, calculations, reminders, or general questions.
            </div>
            <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
              {['What time is it?', 'Tell me a joke', 'What is 25 * 4?', 'Latest news headlines', 'Good morning!'].map(q => (
                <button key={q} onClick={() => setInput(q)} style={{
                  padding: '5px 12px', borderRadius: 20,
                  border: '1px solid rgba(0,200,255,0.2)',
                  background: 'rgba(0,200,255,0.05)', color: '#64748b',
                  fontSize: 11, cursor: 'pointer',
                }}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            display: 'flex',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
            gap: 8, alignItems: 'flex-end',
          }}>
            {m.role === 'assistant' && (
              <div style={{
                width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                background: 'linear-gradient(135deg, #0e7490, #0891b2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Bot size={14} color="#fff" />
              </div>
            )}
            <div style={{
              maxWidth: '70%', padding: '10px 14px', borderRadius: 12,
              background: m.role === 'user'
                ? 'linear-gradient(135deg, #1e3a5f, #1e40af)'
                : 'rgba(255,255,255,0.05)',
              border: m.role === 'user'
                ? '1px solid rgba(59,130,246,0.3)'
                : '1px solid rgba(255,255,255,0.08)',
              color: '#e2e8f0', fontSize: 13, lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
            }}>
              {m.content}
            </div>
            {m.role === 'user' && (
              <div style={{
                width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                background: 'linear-gradient(135deg, #1e3a5f, #1e40af)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <User size={14} color="#fff" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'linear-gradient(135deg, #0e7490, #0891b2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Bot size={14} color="#fff" />
            </div>
            <div style={{
              padding: '10px 14px', borderRadius: 12,
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
              display: 'flex', gap: 4, alignItems: 'center',
            }}>
              {[0, 0.2, 0.4].map((d, i) => (
                <span key={i} style={{
                  width: 6, height: 6, borderRadius: '50%', background: '#00c8ff',
                  animation: `pulse 1.2s ${d}s infinite`,
                }} />
              ))}
            </div>
          </div>
        )}
        {error && (
          <div style={{ color: '#fca5a5', fontSize: 12, padding: '6px 10px',
            background: 'rgba(239,68,68,0.1)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)' }}>
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '12px 16px', borderTop: '1px solid rgba(0,200,255,0.1)',
        display: 'flex', gap: 8,
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Type a message… (Enter to send)"
          disabled={loading}
          style={{
            flex: 1, padding: '11px 14px', borderRadius: 8,
            border: '1px solid rgba(0,200,255,0.2)',
            background: 'rgba(255,255,255,0.04)', color: '#e2e8f0',
            fontSize: 13, outline: 'none',
          }}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          style={{
            padding: '11px 14px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: loading || !input.trim()
              ? 'rgba(0,200,255,0.1)'
              : 'linear-gradient(135deg, #0e7490, #0891b2)',
            color: '#fff', transition: 'all 0.2s',
          }}
        >
          {loading
            ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
            : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Channel Setup Panel (right panel for external channels)
// ---------------------------------------------------------------------------

function ChannelSetupPanel({
  channel,
  base,
  onRefresh,
}: {
  channel: ChannelMeta;
  base: string;
  onRefresh: () => void;
}) {
  const [creds, setCreds] = useState<Record<string, string>>({});
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const isConnected = channel.status === 'connected';

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    setSuccess(false);
    const res = await connectChannel(base, channel.id, creds);
    setConnecting(false);
    if (res.ok) {
      setSuccess(true);
      onRefresh();
    } else {
      setError(res.error ?? 'Connection failed');
    }
  };

  const handleDisconnect = async () => {
    await disconnectChannel(base, channel.id);
    onRefresh();
    setSuccess(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', padding: '24px' }}>
      {/* Channel header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
        <span style={{ fontSize: 36 }}>{channel.icon}</span>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#e2e8f0', marginBottom: 4 }}>
            {channel.name}
          </div>
          <div style={{ fontSize: 13, color: '#64748b' }}>{channel.description}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
            <StatusDot status={channel.status} />
            <span style={{ fontSize: 11, color: statusColor(channel.status) }}>
              {channel.status.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      {/* Setup steps */}
      {channel.setup_steps.length > 0 && (
        <div style={{
          background: 'rgba(0,200,255,0.04)',
          border: '1px solid rgba(0,200,255,0.12)',
          borderRadius: 10, padding: '16px', marginBottom: 20,
        }}>
          <div style={{ fontSize: 11, color: '#00c8ff', letterSpacing: '0.12em', fontWeight: 700, marginBottom: 12 }}>
            SETUP INSTRUCTIONS
          </div>
          {channel.setup_steps.map((step, i) => (
            <div key={i} style={{
              display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 8,
            }}>
              <span style={{
                flexShrink: 0, width: 20, height: 20, borderRadius: '50%',
                background: 'rgba(0,200,255,0.15)', color: '#00c8ff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
              }}>
                {i + 1}
              </span>
              <span style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>{step}</span>
            </div>
          ))}
          {channel.setup_url && (
            <a
              href={channel.setup_url}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 8,
                color: '#00c8ff', fontSize: 12, textDecoration: 'none',
              }}
            >
              <ExternalLink size={12} />
              Open {channel.name} Developer Portal
            </a>
          )}
        </div>
      )}

      {/* Credential fields */}
      {channel.fields.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.12em', fontWeight: 700, marginBottom: 12 }}>
            CREDENTIALS
          </div>
          {channel.fields.map(f => (
            <div key={f.key} style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 11, color: '#64748b', marginBottom: 6 }}>
                {f.label}
              </label>
              <input
                type={f.key.includes('token') || f.key.includes('password') || f.key.includes('secret') ? 'password' : 'text'}
                placeholder={f.placeholder}
                value={creds[f.key] ?? ''}
                onChange={e => setCreds(prev => ({ ...prev, [f.key]: e.target.value }))}
                disabled={isConnected}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  padding: '10px 14px', borderRadius: 8,
                  border: '1px solid rgba(0,200,255,0.2)',
                  background: 'rgba(255,255,255,0.04)', color: '#e2e8f0',
                  fontSize: 12, outline: 'none',
                  opacity: isConnected ? 0.5 : 1,
                }}
              />
            </div>
          ))}
        </div>
      )}

      {/* Error / success */}
      {error && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, marginBottom: 14,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
          color: '#fca5a5', fontSize: 12,
        }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, marginBottom: 14,
          background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)',
          color: '#86efac', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <CheckCircle size={14} />
          Connected! Jarvis will now auto-reply to incoming messages.
        </div>
      )}

      {/* Connect / Disconnect button */}
      <div style={{ display: 'flex', gap: 10 }}>
        {isConnected ? (
          <button
            onClick={handleDisconnect}
            style={{
              padding: '11px 24px', borderRadius: 8, border: 'none', cursor: 'pointer',
              background: 'linear-gradient(135deg, #7f1d1d, #991b1b)',
              color: '#fff', fontWeight: 600, fontSize: 13,
              display: 'flex', alignItems: 'center', gap: 8,
            }}
          >
            <XCircle size={16} /> Disconnect
          </button>
        ) : (
          <button
            onClick={handleConnect}
            disabled={connecting || (channel.fields.length > 0 && channel.fields.some(f => !creds[f.key]))}
            style={{
              padding: '11px 24px', borderRadius: 8, border: 'none', cursor: 'pointer',
              background: connecting
                ? 'rgba(0,200,255,0.1)'
                : 'linear-gradient(135deg, #164e63, #0e7490)',
              color: '#fff', fontWeight: 600, fontSize: 13,
              display: 'flex', alignItems: 'center', gap: 8,
              opacity: (channel.fields.length > 0 && channel.fields.some(f => !creds[f.key])) ? 0.5 : 1,
            }}
          >
            {connecting
              ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Connecting…</>
              : <><Wifi size={16} /> Connect</>}
          </button>
        )}
      </div>

      {/* Info note for channels with no fields (webchat redirects to WebChatPanel) */}
      {channel.fields.length === 0 && channel.id !== 'webchat' && (
        <div style={{
          marginTop: 16, padding: '10px 14px', borderRadius: 8,
          background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)',
          color: '#fde68a', fontSize: 12, display: 'flex', gap: 8, alignItems: 'flex-start',
        }}>
          <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          This channel requires no credentials and will connect immediately.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// WhatsApp Baileys — QR code scan panel
// ---------------------------------------------------------------------------

function WhatsAppBaileysPanel({ base }: { base: string }) {
  const [status, setStatus] = useState('disconnected');
  const [qr, setQr] = useState(''); // base64 PNG
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const pollQr = useCallback(async () => {
    try {
      const r = await fetch(`${base}/api/channels/whatsapp_baileys/qr`);
      if (!r.ok) return;
      const d = await r.json();
      setStatus(d.status);
      setQr(d.qr ?? '');
      if (d.connected) stopPoll();
    } catch { /* network error, keep polling */ }
  }, [base]);

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const r = await fetch(`${base}/api/channels/whatsapp_baileys/connect`, { method: 'POST' });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? r.statusText); }
      // Start polling for QR
      stopPoll();
      pollRef.current = setInterval(pollQr, 2000);
      pollQr();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    stopPoll();
    await fetch(`${base}/api/channels/whatsapp_baileys/disconnect`, { method: 'POST' });
    setStatus('disconnected');
    setQr('');
  };

  useEffect(() => {
    // Check current status on mount
    pollQr();
    return stopPoll;
  }, [pollQr]);

  const isConnected = status === 'connected';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', padding: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
        <span style={{ fontSize: 36 }}>💚</span>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#e2e8f0', marginBottom: 4 }}>
            WhatsApp (Personal)
          </div>
          <div style={{ fontSize: 13, color: '#64748b' }}>
            Connect your personal WhatsApp by scanning a QR code
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
            <StatusDot status={isConnected ? 'connected' : status === 'waiting_qr' ? 'connecting' : 'disconnected'} />
            <span style={{ fontSize: 11, color: isConnected ? '#22c55e' : '#f59e0b' }}>
              {isConnected ? 'CONNECTED — Jarvis auto-replies' :
               status === 'waiting_qr' ? 'SCAN QR CODE' :
               status === 'starting' ? 'STARTING…' : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </div>

      {/* Setup steps */}
      <div style={{
        background: 'rgba(34,197,94,0.04)', border: '1px solid rgba(34,197,94,0.15)',
        borderRadius: 10, padding: '16px', marginBottom: 20,
      }}>
        <div style={{ fontSize: 11, color: '#22c55e', letterSpacing: '0.12em', fontWeight: 700, marginBottom: 12 }}>
          HOW IT WORKS
        </div>
        {[
          'Click Connect below — a QR code will appear',
          'Open WhatsApp on your phone → tap ⋮ → Linked Devices → Link a Device',
          'Point your camera at the QR code',
          'Done! Text anything to yourself or have someone text your number — Jarvis auto-replies',
        ].map((step, i) => (
          <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 8 }}>
            <span style={{
              flexShrink: 0, width: 20, height: 20, borderRadius: '50%',
              background: 'rgba(34,197,94,0.2)', color: '#22c55e',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700,
            }}>{i + 1}</span>
            <span style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>{step}</span>
          </div>
        ))}
      </div>

      {/* QR Code display */}
      {status === 'waiting_qr' && qr && (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          background: '#fff', borderRadius: 12, padding: 20, marginBottom: 20,
          border: '2px solid rgba(34,197,94,0.4)',
          boxShadow: '0 0 30px rgba(34,197,94,0.1)',
        }}>
          <div style={{ fontSize: 12, color: '#334155', marginBottom: 12, fontWeight: 600 }}>
            Scan with WhatsApp
          </div>
          {qr.startsWith('iVBOR') || qr.length > 200 ? (
            <img src={`data:image/png;base64,${qr}`} alt="WhatsApp QR Code"
              style={{ width: 220, height: 220, imageRendering: 'pixelated' }} />
          ) : (
            <div style={{ fontFamily: 'monospace', fontSize: 8, lineHeight: 1.2, color: '#000', wordBreak: 'break-all' }}>
              {qr}
            </div>
          )}
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 12 }}>
            Scanning for new QR every 2s…
          </div>
        </div>
      )}

      {/* Connected state */}
      {isConnected && (
        <div style={{
          padding: '16px', borderRadius: 10, marginBottom: 20,
          background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#86efac', marginBottom: 8 }}>
            <CheckCircle size={16} />
            <span style={{ fontWeight: 600, fontSize: 13 }}>WhatsApp Connected!</span>
          </div>
          <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.7 }}>
            Jarvis is now listening to your WhatsApp messages and will auto-reply.<br />
            You can send commands like:<br />
            <code style={{ color: '#a78bfa' }}>"what time is it"</code>,{' '}
            <code style={{ color: '#a78bfa' }}>"tell me a joke"</code>,{' '}
            <code style={{ color: '#a78bfa' }}>"weather today"</code>,{' '}
            <code style={{ color: '#a78bfa' }}>"latest news"</code>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, marginBottom: 14,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
          color: '#fca5a5', fontSize: 12,
        }}>
          {error}
        </div>
      )}

      {/* Buttons */}
      <div style={{ display: 'flex', gap: 10 }}>
        {isConnected ? (
          <button onClick={handleDisconnect} style={{
            padding: '11px 24px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: 'linear-gradient(135deg, #7f1d1d, #991b1b)',
            color: '#fff', fontWeight: 600, fontSize: 13,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <XCircle size={16} /> Disconnect
          </button>
        ) : (
          <button onClick={handleConnect} disabled={connecting || status === 'waiting_qr' || status === 'starting'} style={{
            padding: '11px 24px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: connecting || status === 'waiting_qr' || status === 'starting'
              ? 'rgba(34,197,94,0.15)'
              : 'linear-gradient(135deg, #14532d, #166534)',
            color: '#fff', fontWeight: 600, fontSize: 13,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            {connecting || status === 'starting'
              ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Starting…</>
              : status === 'waiting_qr'
              ? <><QrCode size={16} /> Waiting for scan…</>
              : <><QrCode size={16} /> Connect WhatsApp</>}
          </button>
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Main ChannelsPage
// ---------------------------------------------------------------------------

export default function ChannelsPage() {
  const base = getBase();
  const [channels, setChannels] = useState<ChannelMeta[]>([]);
  const [selected, setSelected] = useState<string>('webchat');
  const [loading, setLoading] = useState(true);
  const [time, setTime] = useState(() => new Date().toLocaleTimeString());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(t);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    const list = await fetchChannels(base);
    setChannels(list);
    setLoading(false);
  }, [base]);

  useEffect(() => { refresh(); }, [refresh]);
  // Poll status every 5s
  useEffect(() => {
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const selectedChannel = channels.find(c => c.id === selected);
  const connectedCount = channels.filter(c => c.status === 'connected').length;

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a0a0f 0%, #0f0f1a 50%, #0a0a0f 100%)',
      color: '#e2e8f0',
      fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Status bar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 24px', borderBottom: '1px solid rgba(0,200,255,0.15)',
        background: 'rgba(0,0,0,0.4)', fontSize: '11px',
        letterSpacing: '0.1em', color: '#64748b',
      }}>
        <span style={{ color: '#00c8ff', fontWeight: 700 }}>OPENJARVIS · MESSAGING CHANNELS</span>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <span style={{ color: connectedCount > 0 ? '#22c55e' : '#475569' }}>
            {connectedCount} CHANNEL{connectedCount !== 1 ? 'S' : ''} ACTIVE
          </span>
          <button onClick={refresh} title="Refresh" style={{
            background: 'none', border: 'none', color: '#475569', cursor: 'pointer', padding: 2,
          }}>
            <RefreshCw size={11} />
          </button>
          <span>{time}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* ── Left panel: channel list ── */}
        <div style={{
          width: 260, flexShrink: 0, display: 'flex', flexDirection: 'column',
          borderRight: '1px solid rgba(0,200,255,0.1)',
          background: 'rgba(0,0,0,0.2)',
        }}>
          <div style={{ padding: '14px 16px 8px', fontSize: 10, letterSpacing: '0.15em', color: '#475569', fontWeight: 700 }}>
            CHANNELS
          </div>

          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: '#475569' }}>
              <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
            </div>
          ) : (
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {channels.map(ch => (
                <button
                  key={ch.id}
                  onClick={() => setSelected(ch.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    width: '100%', textAlign: 'left', padding: '10px 16px',
                    background: selected === ch.id ? 'rgba(0,200,255,0.08)' : 'transparent',
                    border: 'none', borderLeft: selected === ch.id ? '2px solid #00c8ff' : '2px solid transparent',
                    cursor: 'pointer', color: '#e2e8f0', transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => {
                    if (selected !== ch.id)
                      (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.03)';
                  }}
                  onMouseLeave={e => {
                    if (selected !== ch.id)
                      (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                  }}
                >
                  <span style={{ fontSize: 18, flexShrink: 0 }}>{ch.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: selected === ch.id ? '#e2e8f0' : '#94a3b8' }}>
                      {ch.name}
                    </div>
                    <div style={{ fontSize: 10, color: statusColor(ch.status), display: 'flex', alignItems: 'center', gap: 4 }}>
                      <StatusDot status={ch.status} />
                      {ch.status}
                      {ch.easy && ch.status === 'disconnected' && (
                        <span style={{ color: '#22c55e', marginLeft: 4 }}>· easy</span>
                      )}
                    </div>
                  </div>
                  <ChevronRight size={14} color="#334155" />
                </button>
              ))}
            </div>
          )}

          {/* Legend */}
          <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: 10, color: '#334155' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <StatusDot status="connected" /> connected
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <StatusDot status="disconnected" /> disconnected · <span style={{ color: '#22c55e' }}>easy</span> = no accounts needed
            </div>
          </div>
        </div>

        {/* ── Right panel ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {selected === 'webchat' ? (
            <WebChatPanel base={base} />
          ) : selected === 'whatsapp_baileys' ? (
            <WhatsAppBaileysPanel base={base} />
          ) : selectedChannel ? (
            <ChannelSetupPanel
              key={selected}
              channel={selectedChannel}
              base={base}
              onRefresh={refresh}
            />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: '#334155' }}>
              <div style={{ textAlign: 'center' }}>
                <MessageSquare size={40} style={{ marginBottom: 12, opacity: 0.3 }} />
                <div>Select a channel to get started</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
      `}</style>
    </div>
  );
}
