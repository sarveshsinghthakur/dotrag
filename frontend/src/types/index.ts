export interface Document {
  id: string;
  filename: string;
  page_count: number;
  file_size: number;
  status: 'uploading' | 'processing' | 'indexing' | 'ready' | 'error';
  created_at: string;
  chunk_count: number;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface Citation {
  id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  chunk_id: string;
  text_snippet: string;
  relevance_score: number;
  citation_index: number;
}

export interface ToolExecution {
  id: string;
  tool_name: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  status: string;
  duration_ms: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  tool_executions?: ToolExecution[];
  timestamp: string;
}

export interface Conversation {
  id: string;
  title: string;
  document_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface UploadResponse {
  document: Document;
  message: string;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  citations: Citation[];
  tool_executions: ToolExecution[];
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total_results: number;
}

export interface StreamEvent {
  type: 'status' | 'chunk' | 'citations' | 'conversation_id' | 'done';
  content: string | Citation[];
}
