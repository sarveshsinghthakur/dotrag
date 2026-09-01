import { useState, useRef, useEffect } from 'react';
import {
  ArrowLeft, Send, Loader2, FileText,
  ExternalLink, Paperclip
} from 'lucide-react';
import { api } from '../services/api';
import type { ChatMessage, Citation, Document } from '../types';

interface ChatPanelProps {
  selectedDocIds: string[];
  onBack: () => void;
  documents: Document[];
  onUpload: (file: File) => Promise<unknown>;
  onRefresh: () => void;
}

export default function ChatPanel({ selectedDocIds, onBack, documents, onUpload, onRefresh }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [status, setStatus] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [localDocIds, setLocalDocIds] = useState<string[]>(selectedDocIds);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Sync selectedDocIds with local state
  useEffect(() => {
    setLocalDocIds(selectedDocIds);
  }, [selectedDocIds]);

  // Auto-select all ready documents if none selected
  useEffect(() => {
    if (localDocIds.length === 0 && documents.length > 0) {
      const readyDocs = documents.filter(d => d.status === 'ready');
      if (readyDocs.length > 0) {
        setLocalDocIds(readyDocs.map(d => d.id));
      }
    }
  }, [documents]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const result = await onUpload(file);
      const newDoc = (result as any).document;
      if (newDoc) {
        setLocalDocIds(prev => [...prev, newDoc.id]);
        // Wait for processing and refresh
        setTimeout(() => onRefresh(), 2000);
      }
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);
    setStatus('analyzing query');

    try {
      let fullResponse = '';
      let citations: Citation[] = [];
      let newConversationId = conversationId;

      const stream = api.chatStream(
        input.trim(),
        conversationId,
        localDocIds
      );

      for await (const event of stream) {
        switch (event.type) {
          case 'status':
            setStatus(event.content as string);
            break;
          case 'chunk':
            fullResponse += event.content;
            // Update the last message or create new one
            setMessages(prev => {
              const msgs = [...prev];
              const lastMsg = msgs[msgs.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                msgs[msgs.length - 1] = { ...lastMsg, content: fullResponse };
              } else {
                msgs.push({
                  id: 'assistant-' + Date.now(),
                  role: 'assistant',
                  content: fullResponse,
                  timestamp: new Date().toISOString(),
                });
              }
              return msgs;
            });
            break;
          case 'citations':
            citations = event.content as Citation[];
            setMessages(prev => {
              const msgs = [...prev];
              const lastMsg = msgs[msgs.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                msgs[msgs.length - 1] = { ...lastMsg, citations };
              }
              return msgs;
            });
            break;
          case 'conversation_id':
            newConversationId = event.content as string;
            setConversationId(newConversationId);
            break;
        }
      }
    } catch (err) {
      console.error('Stream error:', err);
      setMessages(prev => [...prev, {
        id: 'error-' + Date.now(),
        role: 'assistant',
        content: 'An error occurred while processing your request.',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setIsStreaming(false);
      setStatus('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const selectedDocs = documents.filter(d => localDocIds.includes(d.id));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-dot-dim/20">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="font-mono text-sm font-bold">Research Session</h2>
            {selectedDocs.length > 0 && (
              <div className="text-xs text-dot-dim">
                Searching {selectedDocs.length} document{selectedDocs.length !== 1 ? 's' : ''}
              </div>
            )}
          </div>
        </div>
        {status && (
          <div className="flex items-center gap-2 text-xs font-mono text-dot-dim">
            <div className="w-2 h-2 bg-white rounded-full status-pulse"></div>
            {status}
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
            <div className="w-12 h-12 border border-dot-dim/30 flex items-center justify-center">
              <FileText className="w-6 h-6 text-dot-dim" />
            </div>
            <div className="space-y-2">
              <p className="font-mono text-sm text-dot-dim">
                Ask anything about your documents
              </p>
              <p className="text-xs text-dot-dim/50 max-w-xs">
                {selectedDocs.length > 0
                  ? `Searching in: ${selectedDocs.map(d => d.filename).join(', ')}`
                  : 'Searching across all uploaded documents'
                }
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`message-enter ${msg.role === 'user' ? 'flex justify-end' : ''}`}
          >
            <div className={`max-w-3xl ${msg.role === 'user' ? 'text-right' : ''}`}>
              {/* Role label */}
              <div className={`text-xs font-mono text-dot-dim mb-2 tracking-wider`}>
                {msg.role === 'user' ? 'YOU' : 'DOTRAG'}
              </div>

              {/* Message content */}
              <div className={`text-sm leading-relaxed whitespace-pre-wrap ${msg.role === 'user' ? '' : ''}`}>
                {msg.content}
                {isStreaming && msg.role === 'assistant' && msg.id === messages[messages.length - 1]?.id && (
                  <span className="cursor-blink"></span>
                )}
              </div>

              {/* Citations */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-4 space-y-2">
                  <div className="text-xs font-mono text-dot-dim tracking-wider">
                    SOURCES
                  </div>
                  <div className="space-y-1">
                    {msg.citations.map((cite, idx) => (
                      <button
                        key={idx}
                        className="flex items-center gap-2 text-xs text-dot-dim hover:text-white
                                   transition-colors group"
                      >
                        <span className="font-mono text-dot-dim/50">
                          {String(idx + 1).padStart(2, '0')}
                        </span>
                        <FileText className="w-3 h-3" />
                        <span>{cite.document_name}</span>
                        <span className="text-dot-dim/50">·</span>
                        <span>p.{cite.page_number}</span>
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-dot-dim/20 p-4">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf"
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || isStreaming}
            className="px-3 py-3 border border-dot-dim/30 hover:border-white/50
                       text-dot-dim hover:text-white transition-colors
                       disabled:opacity-30 disabled:cursor-not-allowed"
            title="Upload PDF"
          >
            {isUploading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Paperclip className="w-4 h-4" />
            )}
          </button>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question..."
            rows={1}
            className="flex-1 bg-dot-dark border border-dot-dim/30 px-4 py-3
                       text-sm font-mono resize-none
                       focus:outline-none focus:border-white/50
                       placeholder:text-dot-dim/30"
            disabled={isStreaming}
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="px-4 py-3 bg-white text-black font-mono text-sm
                       hover:bg-gray-200 transition-colors
                       disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
