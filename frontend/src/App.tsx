import { useState, useEffect } from 'react';
import { api } from './services/api';
import type { Document } from './types';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import PDFViewer from './components/PDFViewer';
import UploadZone from './components/UploadZone';

type View = 'home' | 'chat' | 'viewer';

function App() {
  const [view, setView] = useState<View>('home');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    try {
      const result = await api.uploadDocument(file);
      setDocuments(prev => [result.document, ...prev]);
      return result;
    } catch (err) {
      throw err;
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteDocument(id);
      setDocuments(prev => prev.filter(d => d.id !== id));
      if (selectedDoc?.id === id) setSelectedDoc(null);
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleSelectDoc = (doc: Document) => {
    setSelectedDoc(doc);
    setView('viewer');
  };

  const handleOpenChat = (docIds?: string[]) => {
    if (docIds) setSelectedDocIds(docIds);
    setView('chat');
  };

  return (
    <div className="h-screen flex bg-dot-black text-dot-white overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        documents={documents}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onSelectDoc={handleSelectDoc}
        onOpenChat={handleOpenChat}
        onDelete={handleDelete}
        onUpload={handleUpload}
        onRefresh={loadDocuments}
        selectedDocId={selectedDoc?.id}
        loading={loading}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {view === 'home' && (
          <HomeView
            documents={documents}
            onOpenChat={handleOpenChat}
            onUpload={handleUpload}
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
          />
        )}
      </main>
    </div>
  );
}

function HomeView({
  documents,
  onOpenChat,
  onUpload,
}: {
  documents: Document[];
  onOpenChat: (docIds?: string[]) => void;
  onUpload: (file: File) => Promise<unknown>;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center dot-matrix-bg p-8">
      <div className="max-w-2xl w-full text-center space-y-12">
        {/* Logo */}
        <div className="space-y-4">
          <div className="flex items-center justify-center gap-3">
            <div className="w-3 h-3 bg-white rounded-full"></div>
            <h1 className="text-6xl font-mono font-bold tracking-tighter">
              DOTRAG
            </h1>
            <div className="w-3 h-3 bg-white rounded-full"></div>
          </div>
          <p className="text-dot-dim font-mono text-sm tracking-widest">
            READ. SEARCH. UNDERSTAND.
          </p>
          <p className="text-dot-dim text-sm max-w-md mx-auto">
            Your documents, connected to an AI research assistant.
            Upload PDFs, search across them, and get cited answers.
          </p>
        </div>

        {/* Upload */}
        <UploadZone onUpload={onUpload} />

        {/* Quick Actions */}
        {documents.length > 0 && (
          <div className="space-y-4">
            <button
              onClick={() => {
                const readyDocs = documents.filter(d => d.status === 'ready');
                onOpenChat(readyDocs.map(d => d.id));
              }}
              className="px-8 py-3 border border-white text-white font-mono text-sm
                         hover:bg-white hover:text-black transition-all duration-200
                         tracking-wider uppercase"
            >
              Start Research Session
            </button>

            <div className="text-dot-dim text-xs font-mono">
              {documents.length} document{documents.length !== 1 ? 's' : ''} uploaded
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
