import React, { useState } from 'react';
import { Bot, Send, BookOpen, AlertCircle, Loader2 } from 'lucide-react';
import { finexApiClient } from '../services/apiClient';
import { useAuth } from '../context/AuthContext';

interface Citation {
  chunk_id?: string;
  source_title: string;
  section?: string;
  page?: string;
  doc_date?: string;
  excerpt?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  isRefusal?: boolean;
}

export const ChatPage: React.FC = () => {
  const { user: authUser, isAuthenticated } = useAuth();
  const activeUserName =
    isAuthenticated && authUser?.displayName ? authUser.displayName : 'Investor';

  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: `Hello ${activeUserName}! I am your FinEx Grounded AI Assistant. Ask me any question about portfolio diversification, risk profiling, market terms, or financial goals.`,
      citations: [{ source_title: 'FinEx Investment Curriculum', section: 'Core Principles' }],
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: trimmed,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await finexApiClient.request('/api/v1/ai/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: trimmed }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const result = await response.json();
      const aiData = result.data;

      const botReply: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: aiData.answer_text,
        citations: aiData.citations,
        isRefusal: aiData.intent === 'REFUSAL_FINANCIAL_ADVICE',
      };

      setMessages((prev) => [...prev, botReply]);
    } catch {
      const fallbackReply: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          'Educational guidance: Portfolio risk and asset allocation are computed deterministically. Spreading capital across diverse asset classes helps manage market volatility while building long-term financial rhythm.',
        citations: [{ source_title: 'FinEx Curriculum v1', section: 'Asset Allocation' }],
      };
      setMessages((prev) => [...prev, fallbackReply]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '560px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '20px',
        }}
      >
        <div>
          <p className="local-eyebrow">LEARN &amp; EXPLORE</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            AI Research Assistant (RAG)
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Citation-grounded educational financial intelligence for {activeUserName}
          </p>
        </div>
        <span className="badge badge-info">Grounded RAG</span>
      </div>

      {/* Chat Conversation Container */}
      <div
        className="glass-card"
        style={{
          flex: 1,
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            paddingRight: '8px',
            maxHeight: '420px',
          }}
        >
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '78%',
                padding: '16px 20px',
                borderRadius: '18px',
                background:
                  msg.role === 'user'
                    ? 'var(--color-accent-coral)'
                    : msg.isRefusal
                      ? '#FEF3F2'
                      : 'var(--color-surface-elevated)',
                border:
                  msg.role === 'user'
                    ? 'none'
                    : msg.isRefusal
                      ? '1px solid #FDA29B'
                      : '1px solid var(--color-surface-divider)',
                color: msg.role === 'user' ? '#FFFFFF' : 'var(--color-text)',
                boxShadow: '0 4px 14px rgba(24, 44, 49, 0.05)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '6px',
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  color:
                    msg.role === 'user' ? 'rgba(255,255,255,0.9)' : 'var(--color-text-muted)',
                }}
              >
                {msg.role === 'user' ? (
                  `You (${activeUserName})`
                ) : (
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      color: msg.isRefusal ? '#B42318' : 'var(--color-accent-violet)',
                    }}
                  >
                    <Bot size={14} /> finex* AI
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.96rem', lineHeight: 1.55 }}>{msg.content}</div>

              {msg.citations && msg.citations.length > 0 && (
                <div
                  style={{
                    marginTop: '10px',
                    paddingTop: '8px',
                    borderTop: '1px solid var(--color-surface-divider)',
                    fontSize: '0.76rem',
                    fontWeight: 600,
                    color: 'var(--color-accent-violet)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  {msg.citations.map((c, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <BookOpen size={12} /> Citation: {c.source_title}{' '}
                      {c.section ? `— ${c.section}` : ''}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div
              style={{
                alignSelf: 'flex-start',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: 'var(--color-text-muted)',
                fontSize: '0.88rem',
              }}
            >
              <Loader2 size={16} /> finex* AI is thinking...
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div style={{ marginTop: '20px', display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
          <input
            type="text"
            placeholder="Ask AI about asset allocation, risk, diversification..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            disabled={loading}
            style={{
              flex: '1 1 260px',
              padding: '14px 18px',
              borderRadius: '999px',
              fontSize: '0.95rem',
            }}
          />
          <button onClick={handleSend} disabled={loading} className="btn-primary">
            {loading ? <Loader2 size={18} /> : <Send size={18} />} Send
          </button>
        </div>

        <div
          style={{
            marginTop: '12px',
            fontSize: '0.75rem',
            color: 'var(--color-text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <AlertCircle size={13} /> AI responses provide educational decision support, not
          guaranteed financial advice.
        </div>
      </div>
    </div>
  );
};
