const API_BASE = import.meta.env.VITE_API_URL || '/api';

export const api = {
  async uploadDocument(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Upload failed');
    return res.json();
  },

  async getDocuments() {
    const res = await fetch(`${API_BASE}/documents/`);
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  async getDocument(id: string) {
    const res = await fetch(`${API_BASE}/documents/${id}`);
    if (!res.ok) throw new Error('Document not found');
    return res.json();
  },

  async deleteDocument(id: string) {
    const res = await fetch(`${API_BASE}/documents/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete');
    return res.json();
  },

  async search(query: string, documentIds: string[] = [], topK: number = 8) {
    const res = await fetch(`${API_BASE}/search/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, document_ids: documentIds, top_k: topK }),
    });
    if (!res.ok) throw new Error('Search failed');
    return res.json();
  },

  async chat(message: string, conversationId?: string, documentIds: string[] = []) {
    const res = await fetch(`${API_BASE}/chat/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: conversationId, document_ids: documentIds }),
    });
    if (!res.ok) throw new Error('Chat failed');
    return res.json();
  },

  async *chatStream(message: string, conversationId?: string, documentIds: string[] = []) {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: conversationId, document_ids: documentIds }),
    });

    if (!res.ok) throw new Error('Stream failed');

    const reader = res.body?.getReader();
    if (!reader) throw new Error('No reader');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            yield data;
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  },

  async getDocumentPage(documentId: string, pageNumber: number) {
    const res = await fetch(`${API_BASE}/documents/${documentId}/pages/${pageNumber}`);
    if (!res.ok) throw new Error('Failed to fetch page');
    return res.json();
  },

  getDocumentFileUrl(documentId: string) {
    return `${API_BASE}/documents/${documentId}/file`;
  },
};
