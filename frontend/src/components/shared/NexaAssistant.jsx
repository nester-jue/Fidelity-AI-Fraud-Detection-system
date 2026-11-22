import { useState, useEffect, useRef } from 'react';
import { MessageSquare, X, Send, RotateCcw, Loader2, Sparkles, ShieldCheck } from 'lucide-react';
import { api } from '../../api/apiClient.js';

// Suggested starter questions per role (server is the authority; this mirrors
// the backend's /chatbot/suggested-questions payloads for initial display).
const ROLE_SUGGESTED = {
  claims_officer: [
    'Which documents are missing from my assigned claims?',
    'What is the status of my assigned claims?',
    'Show me the fraud risk scores of my assigned claims.',
  ],
  claims_manager: [
    'Show me the outstanding claims awaiting departmental review.',
    'Which claims in the Claims department have fraud alerts?',
    'What is the processing performance of my Claims department?',
  ],
  fraud_investigator: [
    'Explain why this claim received a critical fraud-risk score.',
    'Show me my open investigations.',
    'Summarise the evidence recorded for an investigation.',
  ],
  compliance_officer: [
    'Which cases have outstanding compliance requirements?',
    'Summarise the latest audit observations.',
    'Which claims are missing documentation?',
  ],
  management: [
    "Summarise the organisation's fraud detection performance.",
    'Which areas currently present the highest fraud exposure?',
  ],
  system_admin: [
    'Are all AI and document-processing services operational?',
    'Show me the latest audit logs.',
  ],
};

const fmtTime = (iso) => {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
};

/**
 * NEXA AI Intelligence Assistant — role-aware conversational assistant.
 * Mounted globally on the authenticated dashboard. All queries go through
 * /chatbot/* API endpoints; the backend enforces role permissions.
 */
export default function NexaAssistant({ user }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [suggested, setSuggested] = useState(ROLE_SUGGESTED[user?.role || 'claims_officer'] || []);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  // Typing process state — when asked, the answer is revealed progressively.
  const [typing, setTyping] = useState(null); // { id, target, text }
  const messagesEndRef = useRef(null);

  // Drive the progressive typing animation while a response is being revealed.
  useEffect(() => {
    if (!typing) return;
    if (typing.text.length >= typing.target.length) {
      setTyping(null);
      return;
    }
    const timer = setInterval(() => {
      setTyping((t) => {
        if (!t) return t;
        const step = Math.min(5, t.target.length - t.text.length);
        if (step <= 0) return { ...t, text: t.target };
        return { ...t, text: t.text + t.target.slice(t.text.length, t.text.length + step) };
      });
    }, 22);
    return () => clearInterval(timer);
  }, [typing]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, open]);

  const loadHistory = async () => {
    try {
      const res = await api.chatHistory();
      if (res.ok) {
        const data = await res.json();
        setMessages(
          data.map((m, i) => ({
            id: `hist-${i}`,
            from: m.direction === 'assistant' ? 'assistant' : 'user',
            text: m.content,
            time: m.created_at,
          }))
        );
      }
    } catch {
      // History is an enhancement; silently continue on failure.
    }
  };

  useEffect(() => {
    if (open) loadHistory();
  }, [open]);

  const send = async (overrideText) => {
    const text = (overrideText ?? input).trim();
    if (!text || loading || typing) return;
    setInput('');
    setError('');
    setLoading(true);
    const userMsg = { id: `u-${Date.now()}`, from: 'user', text, time: new Date().toISOString() };
    setMessages((m) => [...m, userMsg]);
    try {
      const res = await api.chatSendMessage(text);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Chatbot request failed');
      }
      const data = await res.json();
      const msgId = `a-${Date.now()}`;
      setMessages((m) => [...m, { id: msgId, from: 'assistant', text: data.response, time: new Date().toISOString() }]);
      // Reveal the answer progressively — the user sees a typing process.
      setTyping({ id: msgId, target: data.response || '', text: '' });
      if (data.suggestions?.length) setSuggested(data.suggestions);
      if (data.ai_mode && data.ai_mode !== 'deterministic') {
        setMessages((m) => [...m, {
          id: `note-${Date.now()}`, from: 'assistant',
          text: data.ai_mode === 'llm'
            ? '— answered by the configured NEXA AI assistant —'
            : '— answered from verified records —',
          time: null, isNote: true,
        }]);
      }
    } catch (err) {
      setMessages((m) => [...m, {
        id: `e-${Date.now()}`, from: 'assistant',
        text: "I couldn't process that right now. Please try again or contact IT support.",
        time: new Date().toISOString(), isError: true,
      }]);
      setError(err.message || 'Unable to send message.');
    } finally {
      setLoading(false);
    }
  };

  const resetConversation = async () => {
    setMessages([]);
    setError('');
    setSuggested(ROLE_SUGGESTED[user?.role || 'claims_officer'] || []);
    try {
      await api.chatResetHistory();
    } catch { /* best effort */ }
  };

  const roleLabel = user ? `${user.role}` : 'none';

  return (
    <>
      {/* Floating Chat Button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed right-6 bottom-6 z-40 w-14 h-14 rounded-full bg-gradient-to-br from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 shadow-lg flex items-center justify-center hover:scale-105 transition-all"
          title="NEXA AI Intelligence Assistant"
          aria-label="Open NEXA AI Intelligence Assistant"
        >
          <MessageSquare size={22} className="text-slate-950" />
        </button>
      )}

      {/* Chat Window */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-stretch justify-end sm:justify-end">
          {/* Overlay (click closes) */}
          <div className="fixed inset-0 bg-black/20 -z-10" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="flex flex-col w-full sm:w-[420px] h-[80vh] max-h-[620px] sm:h-[580px] rounded-t-2xl sm:rounded-2xl border border-slate-200 shadow-2xl bg-white">
            {/* Header */}
            <div className="bg-[#0A192F] text-white px-5 py-4 flex items-center justify-between rounded-t-2xl sm:rounded-t-2xl">
              <div className="min-w-0">
                <div className="flex items-center space-x-2">
                  <ShieldCheck size={18} className="text-amber-400 flex-shrink-0" />
                  <span className="font-extrabold tracking-wide text-white truncate">NEXA AI Intelligence Assistant</span>
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5">Role-aware · reads real records only</p>
              </div>
              <div className="flex items-center space-x-2 flex-shrink-0">
                <button
                  onClick={resetConversation}
                  title="New conversation"
                  aria-label="New conversation"
                  className="p-1.5 rounded-lg hover:bg-slate-700 transition"
                >
                  <RotateCcw size={15} className="text-slate-300" />
                </button>
                <button
                  onClick={() => setOpen(false)}
                  title="Close assistant"
                  aria-label="Close assistant"
                  className="p-1.5 rounded-lg hover:bg-slate-700 transition"
                >
                  <X size={17} className="text-slate-300" />
                </button>
              </div>
            </div>

            {/* Role badge */}
            <div className="px-5 py-2 border-b border-slate-100 bg-slate-50">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Active role: {roleLabel}
              </p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50">
              {messages.length === 0 && !loading && (
                <div className="text-center text-sm text-slate-400 p-6 space-y-2">
                  <Sparkles size={20} className="mx-auto text-slate-300" />
                  <p className="font-semibold text-slate-500">Ask about your claims, fraud risk, investigations or performance.</p>
                  <p className="text-xs text-amber-600 font-medium">Try: {suggested[0] || 'what can you help with?'}</p>
                </div>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`flex ${m.from === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm whitespace-pre-line shadow-sm ${
                      m.from === 'user'
                        ? 'bg-amber-500 text-slate-950 font-medium'
                        : m.isNote
                          ? 'bg-transparent text-slate-400 italic text-[11px] px-2'
                          : m.isError
                            ? 'bg-red-50 border border-red-200 text-red-700'
                            : 'bg-white text-slate-800'
                    }`}
                  >
                    {m.from === 'user' && <div className="text-[10px] opacity-75 mb-1 text-right font-bold uppercase tracking-wider">YOU</div>}
                    <div className={m.from === 'user' ? 'text-right' : 'text-left'}>
                      {typing && typing.id === m.id ? (
                        <span>{typing.text}<span className="inline-block w-[5px] h-[17px] bg-amber-500 rounded-sm animate-pulse ml-0.5 align-baseline" /></span>
                      ) : (
                        m.text
                      )}
                    </div>
                    {m.time && <div className="text-[9px] opacity-50 mt-1 text-right">{fmtTime(m.time)}</div>}
                  </div>
                </div>
              ))}
              {(loading || typing) && (
                <div className="flex justify-start">
                  <div className="px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-400 flex items-center gap-0.5">
                    {loading && !typing ? (
                      <>
                        <Loader2 size={13} className="animate-spin mr-1.5" />
                        <span className="text-[11px] font-bold">Thinking…</span>
                      </>
                    ) : (
                      <span className="text-[11px] font-bold flex items-center gap-1">
                        <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce" />
                        <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                        <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
                        NEXA AI is typing…
                      </span>
                    )}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Suggested questions */}
            {suggested.length > 0 && (
              <div className="px-4 py-2.5 flex flex-wrap gap-1.5 border-t border-slate-100 bg-white">
                {suggested.slice(0, 3).map((q, i) => (
                  <button
                    key={i}
                    onClick={() => send(q)}
                    disabled={loading || typing}
                    className="text-[11px] px-2.5 py-1 rounded-full border border-amber-300 text-amber-800 bg-amber-50 hover:bg-amber-100 font-medium disabled:opacity-40 transition"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            {/* Error banner */}
            {error && (
              <p className="px-4 pb-1 text-[11px] text-red-600 font-bold" role="alert">
                {error}
              </p>
            )}

            {/* Input */}
            <div className="p-3 border-t border-slate-200 bg-white flex items-center space-x-2 rounded-b-2xl sm:rounded-b-2xl">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="Ask a question…"
                rows={2}
                className="flex-1 text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400 resize-none bg-slate-50"
                aria-label="Message the assistant"
              />
              <button
                onClick={() => send()}
                disabled={loading || typing || !input.trim()}
                className="p-2.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-950 disabled:opacity-40 transition flex-shrink-0"
                aria-label="Send message"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
