import { useState, useEffect, useCallback } from 'react';
import { api } from './services/api';
import type { Document, UploadOptions } from './types';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import PDFViewer from './components/PDFViewer';
import UploadZone from './components/UploadZone';
import {
  MessageSquare, Search, Layers, ArrowRight,
  BookOpen, Zap, Upload, Image as ImageIcon,
} from 'lucide-react';

type View = 'home' | 'chat' | 'viewer';

function App() {
  const [view, setView] = useState<View>('home');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [activeConversationId, setActiveConversationId] = useState<string | undefined>();

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll for status updates on processing documents
  useEffect(() => {
    const processing = documents.some(
      (d) => d.status === 'processing' || d.status === 'indexing' || d.status === 'uploading'
    );
    if (!processing) return;
    const timer = setTimeout(() => loadDocuments(), 3000);
    return () => clearTimeout(timer);
  }, [documents, loadDocuments]);

  const handleUpload = async (file: File, options: UploadOptions = { scope: 'library' }) => {
    const result = await api.uploadDocument(file, options);
    setDocuments((prev) => {
      // Avoid duplicate if already present
      const exists = prev.some((d) => d.id === result.document.id);
      return exists ? prev : [result.document, ...prev];
    });
    return result;
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      if (selectedDoc?.id === id) {
        setSelectedDoc(null);
        setView('home');
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleSelectDoc = (doc: Document) => {
    setSelectedDoc(doc);
    if (doc.file_type === 'pdf') {
      setView('viewer');
    }
  };

  const handleOpenChat = (docIds?: string[]) => {
    if (docIds) setSelectedDocIds(docIds);
    // Reset conversation so each new session starts fresh
    setActiveConversationId(undefined);
    setView('chat');
  };

  const handleConversationIdChange = (id: string) => {
    setActiveConversationId(id);
    // Reload docs so sidebar shows any chat-scoped docs
    loadDocuments();
  };

  return (
    <div className="h-screen flex bg-dot-black text-dot-white overflow-hidden">
      <Sidebar
        documents={documents}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((o) => !o)}
        onSelectDoc={handleSelectDoc}
        onOpenChat={handleOpenChat}
        onDelete={handleDelete}
        onUpload={handleUpload}
        onRefresh={loadDocuments}
        selectedDocId={selectedDoc?.id}
        loading={loading}
        activeConversationId={activeConversationId}
      />

      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {view === 'home' && (
          <HomeView
            documents={documents}
            loading={loading}
            onOpenChat={handleOpenChat}
            onUpload={handleUpload}
            onOpenSidebar={() => setSidebarOpen(true)}
            sidebarOpen={sidebarOpen}
          />
        )}

        {view === 'viewer' && selectedDoc && (
          <PDFViewer
            document={selectedDoc}
            onBack={() => setView('home')}
            onOpenChat={() => handleOpenChat([selectedDoc.id])}
          />
        )}

        {view === 'chat' && (
          <ChatPanel
            selectedDocIds={selectedDocIds}
            onBack={() => setView('home')}
            documents={documents}
            onUpload={handleUpload}
            onRefresh={loadDocuments}
            conversationId={activeConversationId}
            onConversationIdChange={handleConversationIdChange}
          />
        )}
      </main>
    </div>
  );
}

// ─── HomeView ─────────────────────────────────────────────────────────────────
interface HomeViewProps {
  documents: Document[];
  loading: boolean;
  onOpenChat: (docIds?: string[]) => void;
  onUpload: (file: File, options?: UploadOptions) => Promise<unknown>;
  onOpenSidebar: () => void;
  sidebarOpen: boolean;
}

function HomeView({ documents, loading, onOpenChat, onUpload }: HomeViewProps) {
  const readyDocs      = documents.filter((d) => d.status === 'ready');
  const processingDocs = documents.filter((d) => d.status === 'processing' || d.status === 'indexing');
  const libraryDocs    = readyDocs.filter((d) => d.scope === 'library');

  return (
    <div className="flex-1 overflow-y-auto dot-matrix-bg">
      <div className="min-h-full flex flex-col items-center justify-start py-16 px-6">
        <div className="max-w-2xl w-full space-y-12">

          {/* ── Logo / Hero ── */}
          <div className="text-center space-y-5">
            <div className="flex items-center justify-center gap-4">
              <div className="w-2.5 h-2.5 bg-white rounded-full status-pulse" />
              <h1 className="text-5xl md:text-6xl font-mono font-bold tracking-tighter">DOTRAG</h1>
              <div className="w-2.5 h-2.5 bg-white rounded-full status-pulse [animation-delay:1s]" />
            </div>
            <p className="font-mono text-xs tracking-[0.3em] text-dot-dim uppercase">
              Read · Search · Understand
            </p>
            <p className="text-sm text-dot-dim/70 max-w-sm mx-auto leading-relaxed">
              Upload PDFs and images, ask questions, and get cited answers powered by AI.
              Library files are shared across all chats; per-chat files stay private to that session.
            </p>
          </div>

          {/* ── Feature pills ── */}
          <div className="flex flex-wrap justify-center gap-2">
            {[
              { icon: BookOpen,     label: 'PDF Reader'        },
              { icon: ImageIcon,    label: 'Image Analysis'    },
              { icon: Search,       label: 'Semantic Search'   },
              { icon: MessageSquare,label: 'AI Chat'           },
              { icon: Zap,          label: 'Streaming Answers' },
              { icon: Layers,       label: 'Multi-Document'    },
            ].map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-white/8 bg-white/3 text-xs font-mono text-dot-dim"
              >
                <Icon className="w-3 h-3" />
                {label}
              </div>
            ))}
          </div>

          {/* ── Upload zone ── */}
          <div>
            <UploadZone onUpload={(f) => onUpload(f, { scope: 'library' })} />
          </div>

          {/* ── Quick actions ── */}
          {!loading && documents.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center gap-3 before:flex-1 before:h-px before:bg-white/8 after:flex-1 after:h-px after:bg-white/8">
                <span className="text-xs font-mono text-dot-dim/50 px-2">or</span>
              </div>

              <button
                onClick={() => onOpenChat(libraryDocs.map((d) => d.id))}
                disabled={readyDocs.length === 0}
                className="group w-full flex items-center justify-between px-5 py-4
                           border border-white/15 hover:border-white/40 bg-white/3 hover:bg-white/6
                           transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 border border-white/20 flex items-center justify-center bg-white/5">
                    <MessageSquare className="w-4 h-4" />
                  </div>
                  <div className="text-left">
                    <p className="font-mono text-sm font-medium">Start Research Chat</p>
                    <p className="text-xs text-dot-dim mt-0.5">
                      {readyDocs.length > 0
                        ? `${readyDocs.length} document${readyDocs.length !== 1 ? 's' : ''} ready`
                        : 'No documents ready yet'}
                    </p>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-dot-dim group-hover:text-white group-hover:translate-x-1 transition-all" />
              </button>

              {/* Stats */}
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: 'Total',      value: documents.length,        icon: Layers       },
                  { label: 'Ready',      value: readyDocs.length,        icon: Zap          },
                  { label: 'Processing', value: processingDocs.length,   icon: Upload       },
                  { label: 'Library',    value: libraryDocs.length,      icon: BookOpen     },
                ].map(({ label, value, icon: Icon }) => (
                  <div key={label} className="flex flex-col items-center gap-1.5 p-3 border border-white/8 bg-white/2">
                    <Icon className="w-4 h-4 text-dot-dim" />
                    <span className="font-mono text-lg font-bold">{value}</span>
                    <span className="text-xs font-mono text-dot-dim/60">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!loading && documents.length === 0 && (
            <div className="text-center space-y-2 py-4">
              <p className="text-xs font-mono text-dot-dim/40">
                Upload your first document to get started
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
