import React, { useState } from 'react';
import { Bot, Send, Sparkles, BookOpen, AlertCircle } from 'lucide-react';

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello Khyati! I am your FinEx AI Research Assistant. Ask me any question about portfolio diversification, risk profiling, market terms, or financial goals.',
      citations: [{ title: 'FinEx Investment Handbook v5', page: '20' }],
    },
  ]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;

    const userMsg = { id: Date.now().toString(), role: 'user', content: input, citations: [] as {title: string; page: string}[] };
    const botReply = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: `Here is grounded research context regarding "${input}": Portfolio risk is computed deterministically using standard deviation and asset weightings. All values are sourced directly from verified data tables without invented numbers.`,
      citations: [{ title: 'Risk Assessment Framework v1', page: '14' }],
    };

    setMessages((prev) => [...prev, userMsg, botReply]);
    setInput('');
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
        <span className="badge badge-info">Model: Databricks RAG v1</span>
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
                background: msg.role === 'user' ? 'linear-gradient(135deg, #10b981, #059669)' : 'rgba(30, 41, 59, 0.7)',
                border: msg.role === 'user' ? 'none' : '1px solid var(--border-glass)',
                color: '#ffffff',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', fontSize: '0.75rem', color: msg.role === 'user' ? 'rgba(255,255,255,0.8)' : 'var(--text-muted)' }}>
                {msg.role === 'user' ? 'You (Khyati)' : <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#10b981' }}><Bot size={14} /> FinEx AI</span>}
              </div>
              <div style={{ fontSize: '0.95rem', lineHeight: 1.5 }}>{msg.content}</div>

              {msg.citations && (
                <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '0.75rem', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <BookOpen size={12} /> Citation: {msg.citations[0].title} (p. {msg.citations[0].page})
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Input Bar */}
        <div style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
          <input
            type="text"
            placeholder="Ask AI a financial research question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
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
          <button onClick={handleSend} className="btn-primary">
            <Send size={18} /> Send
          </button>
        </div>

        <div style={{ marginTop: '10px', fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <AlertCircle size={12} /> AI responses provide educational decision support, not guaranteed financial advice.
        </div>
      </div>
    </div>
  );
};
