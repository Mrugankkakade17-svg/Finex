import React, { useState } from 'react';
import { Bot, Send, BookOpen, AlertCircle, Loader2 } from 'lucide-react';

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
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello! I am your FinEx Grounded AI Assistant. Ask me any question about portfolio diversification, risk profiling, market terms, or financial goals.',
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
      const response = await fetch('http://127.0.0.1:8000/api/v1/ai/chat', {
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
    } catch (err: any) {
      const fallbackReply: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Educational guidance: Portfolio risk and asset allocation are computed deterministically. Spreading capital across diverse asset classes helps manage market volatility. (${err?.message || 'Offline mode'})`,
        citations: [{ source_title: 'FinEx Curriculum v1', section: 'Asset Allocation' }],
      };
      setMessages((prev) => [...prev, fallbackReply]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>AI Research Assistant (RAG)</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Citation-grounded educational financial intelligence
          </p>
        </div>
        <span className="badge badge-info">Model: Grounded RAG v1</span>
      </div>

      {/* Chat Conversation Container */}
      <div className="glass-card" style={{ flex: 1, padding: '24px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '8px' }}>
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '75%',
                padding: '16px 20px',
                borderRadius: '16px',
                background: msg.role === 'user'
                  ? 'linear-gradient(135deg, #10b981, #059669)'
                  : msg.isRefusal
                  ? 'rgba(239, 68, 68, 0.15)'
                  : 'rgba(30, 41, 59, 0.7)',
                border: msg.role === 'user'
                  ? 'none'
                  : msg.isRefusal
                  ? '1px solid #ef4444'
                  : '1px solid var(--border-glass)',
                color: '#ffffff',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', fontSize: '0.75rem', color: msg.role === 'user' ? 'rgba(255,255,255,0.8)' : 'var(--text-muted)' }}>
                {msg.role === 'user' ? 'You' : <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: msg.isRefusal ? '#ef4444' : '#10b981' }}><Bot size={14} /> FinEx AI</span>}
              </div>
              <div style={{ fontSize: '0.95rem', lineHeight: 1.5 }}>{msg.content}</div>

              {msg.citations && msg.citations.length > 0 && (
                <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '0.75rem', color: 'var(--accent-cyan)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {msg.citations.map((c, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <BookOpen size={12} /> Citation: {c.source_title} {c.section ? `— ${c.section}` : ''}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              <Loader2 size={16} className="animate-spin" /> FinEx AI is thinking...
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
          <input
            type="text"
            placeholder="Ask AI about asset allocation, risk, diversification..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            disabled={loading}
            style={{
              flex: 1,
              padding: '14px 18px',
              borderRadius: '12px',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-glass)',
              color: '#ffffff',
              fontSize: '0.95rem',
            }}
          />
          <button onClick={handleSend} disabled={loading} className="btn-primary">
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />} Send
          </button>
        </div>

        <div style={{ marginTop: '10px', fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <AlertCircle size={12} /> AI responses provide educational decision support, not guaranteed financial advice.
        </div>
      </div>
    </div>
  );
};
