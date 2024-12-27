# PDF Question-Answering Backend

A FastAPI backend service that enables real-time question-answering over uploaded PDF documents using WebSockets. Uses Gemini for text generation and ChromaDB for vector storage.

## Core Features

- PDF upload endpoint with file validation and metadata storage
- WebSocket endpoint for real-time Q&A
- Session-based document management
- Rate limiting for both HTTP and WebSocket endpoints
- Automatic cleanup of uploaded files after WebSocket disconnection

## Technical Stack

- **Framework**: FastAPI
- **Database**: SQLite(for document metadata) + ChromaDB (vector store)
- **File Storage**: Local filesystem
- **LLM**: Google Gemini 1.5
- **Rate Limiting**: Redis
- **Testing**: pytest with async support


Handles file validation, storage, and session initialization.

## Testing

Comprehensive test suite covering:
- File upload validation
- WebSocket lifecycle
- Rate limiting
- PDF processing
- Session cleanup


## Setup

1. Install dependencies:
```bash
poetry install
```

2. Start Redis:
```bash
docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
```

3. Set environment variables:
```bash
GEMINI_API_KEY=your_api_key
```

4. Run server:
```bash
poetry run fastapi run app/main.py --reload
```

5. Run tests:
```bash
pytest app/test_main.py -v
```
