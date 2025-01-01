# PDF Question-Answering Backend

A FastAPI backend service that enables real-time question-answering over uploaded PDF documents using WebSockets. Uses Gemini for text generation and ChromaDB for vector storage.


## Backend Deployment link
https://ai-planet-backend-h3cw.onrender.com/ 

> Free service of render is very slow to boot up.

Both file upload and websockets are hosted on this server. This link opens up a basic html with an upload button. For full functionality, the frontend (frontend/index.html) must be hosted on some other server or locally.

To serve the frontend locally:
```bash
cd frontend
python -m http.server 9000
```
> This frontend is currently configured to work with locally hosted backend. It can be changed to use the deployed backend by changing the url in the fetch requrests.


## Demo
https://github.com/codeblech/AI_Planet_backend/raw/refs/heads/main/screenshots/vid.mp4

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

2. Start Redis (Assuming Docker is installed):
```bash
docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
```

3. Set environment variables:
```bash
GEMINI_API_KEY=your_api_key
```

4. Run server:
```bash
poetry run fastapi run app/main.py
```

5. Run tests:
```bash
pytest app/test_main.py -v
```

6. Docs available at:
```bash
http://localhost:8000/docs
```
and
```bash
http://localhost:8000/redoc
```


# My mental notes while building this project.

## Design Decisions

### auth
not required as per requirements.

### fastapi limiter
https://github.com/long2ice/fastapi-limiter \
last updated: 11 months ago -> unmaintainted?, supports websockets -> chosen

### slowapi
https://github.com/laurents/slowapi
more active, used by many popular projects, but doesn't support websockets -> not chosen

### redis
> https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/docker/
> - redis/redis-stack contains both Redis Stack server and Redis Insight. This container is best for local development because you can use the embedded Redis Insight to visualize your data. \
> `docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest`
>
> - redis/redis-stack-server provides Redis Stack server only. This container is best for production deployment. \
> `docker run -d --name redis-stack-server -p 6379:6379 redis/redis-stack-server:latest`


hence, we'll use redis/redis-stack for local development.

### extracting only text
only extracting text from pdfs as the requirement says.

### LangChain bad
This is my third time trying to use LangChain. Now I've come to the conclusion that it is not worth the hassle. It is much simpler to implement the AI stuff without it. I tried to use LangChain for the pdf processing, but this library somehow manages to break every single thing it aims to optimize. 
Further, it has a lot of dependencies and bloat which makes it totally unsuitable for production.

### LlamaIndex?
The docs are horrible. And the library suffers from the same problems as LangChain. Too much abstraction. 

### But the requirement says to use LangChain/LlamaIndex
I tried to come up with the best solution in the limited time constraint. In a case where some infra is already setup in LangChain/LlamaIndex, I would've used it.

### ephemeral document storage
once some kind of user auth is implemented we can make the document storage persistent. But since the current requirement does not mention user auth, we'll just delete the files after the user disconnects.

### background tasks
converting pdfs to text and storing them in the vector database can be done in the background. This is because the user is not waiting for the pdfs to be converted and stored, and the conversion and storage is not the main functionality of the app.

## Future Improvements

### template
https://github.com/fastapi/full-stack-fastapi-template/tree/master \
might be useful for future full-stack projects.

### periodic cleanup up uploads folder
in case that the client uploads files, but doesn't establish the websocket connection, the uploaded documents remain saved. These can be later deleted using a periodic cleanup task, which can be easily implemented using a cron job.

### UI
show in the ui that pdfs and questions are being processed. But that's not the part of the requirement.

## Notes

### issue with pytest and fastapi-limiter
https://github.com/long2ice/fastapi-limiter/issues/51

### serving the frontend
if frontend is served from a live server like that in vscode, then it must be made sure that the upload folder is not served from that server. this is because the creation of new file in the upload folder will trigger a reload of the frontend, which will break the websocket connection.

### langchain docs
> A note on multimodal models
> Many modern LLMs support inference over multimodal inputs (e.g., images). In some applications -- such as question-answering over PDFs with complex layouts, diagrams, or scans -- it may be advantageous to skip the PDF parsing, instead casting a PDF page to an image and passing it to a model directly.

### For more granular control over pdf parsing
https://python.langchain.com/docs/how_to/document_loader_pdf/

### LangChain chatbot tutorial
https://python.langchain.com/docs/tutorials/chatbot/


### Screenshosts
<p align="center">
<img src="/home/dushyantmalik/Documents/Programming/ai planet/AI_Planet_backend/screenshots/doc.png" width="500">
<img src="/home/dushyantmalik/Documents/Programming/ai planet/AI_Planet_backend/screenshots/fastapi.png" width="500">
<img src="/home/dushyantmalik/Documents/Programming/ai planet/AI_Planet_backend/screenshots/front.png" width="500">
<img src="/home/dushyantmalik/Documents/Programming/ai planet/AI_Planet_backend/screenshots/redis.png" width="500">


