# DotRAG — AI Document Research Platform

Intelligent PDF reader, document search engine, and AI research assistant powered by LangGraph, Mistral AI, and vector search.

## Architecture

```
                    ┌─────────────────────┐
                    │     React UI        │
                    │  Dot-Matrix Design  │
                    └──────────┬──────────┘
                               │
                         REST / SSE
                               │
                    ┌──────────▼──────────┐
                    │      FastAPI        │
                    │      Backend        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     LangGraph       │
                    │   Agent Workflow    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        PDF Retrieval     AI Tools        Mistral API
              │                │
              ▼                ▼
        Vector Database    Tool Functions
              │
              ▼
       Document Chunks
```

## Features

- PDF upload and text extraction
- OCR fallback for scanned documents
- Intelligent chunking with metadata preservation
- Vector embeddings via Mistral API
- Qdrant vector database for search
- LangGraph agent orchestration
- Multiple AI tools (search, summarize, compare, extract)
- Source citations with clickable references
- Streaming AI responses
- Real-time processing status
- Responsive dot-matrix UI design

## Setup

### 1. Clone and configure

```bash
cd dotrag
cp .env.example .env
# Edit .env with your Mistral API key
```

### 2. Environment Variables

```env
MISTRAL_API_KEY=your_mistral_api_key_here
MISTRAL_CHAT_MODEL=mistral-large-latest
MISTRAL_EMBEDDING_MODEL=mistral-embed
DATABASE_URL=postgresql://dotrag:dotrag@localhost:5432/dotrag
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
```

### 3. Run with Docker

```bash
docker compose up --build
```

Access at: http://localhost

### 4. Run Locally

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Access at: http://localhost:5173

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/documents/upload | Upload PDF |
| GET | /api/documents/ | List documents |
| GET | /api/documents/{id} | Get document |
| DELETE | /api/documents/{id} | Delete document |
| POST | /api/search/ | Search documents |
| POST | /api/chat/ | Chat with AI |
| POST | /api/chat/stream | Streaming chat |
| GET | /api/documents/{id}/pages/{page} | Get page |
| GET | /health | Health check |

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

## Tech Stack

- **Backend**: Python, FastAPI, LangGraph, PyMuPDF, Qdrant
- **Frontend**: React, TypeScript, Tailwind CSS
- **AI**: Mistral API (chat + embeddings)
- **Vector DB**: Qdrant
- **Infrastructure**: Docker, PostgreSQL, Redis
