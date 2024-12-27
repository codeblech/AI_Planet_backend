from typing import Annotated
from fastapi import FastAPI, File, UploadFile, status, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from pathlib import Path
import uuid
import aiofiles
from typing import Dict, Set
import sys
from sqlalchemy import create_engine, Column, String, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, UTC

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB in bytes
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Add custom exception classes
class FileUploadError(Exception):
    def __init__(self, filename: str, message: str):
        self.filename = filename
        self.message = message
        super().__init__(self.message)

class FileSizeError(FileUploadError):
    pass

class FileTypeError(FileUploadError):
    pass

# Add connection manager class
class WebSocketConnectionManager:
    def __init__(self):
        self.active_websocket_connections: Dict[str, WebSocket] = {}
        self.authorized_upload_sessions: Set[str] = set()
        self.established_websocket_sessions: Set[str] = set()

    async def connect_websocket(self, websocket: WebSocket, session_id: str):
        print(f"Attempting to connect session {session_id}")  # Debug line
        print(f"Authorized sessions: {self.authorized_upload_sessions}")  # Debug line
        if session_id not in self.authorized_upload_sessions:
            print(f"Session {session_id} not authorized")  # Debug line
            await websocket.close(code=1008, reason="Upload documents first")
            return False
        await websocket.accept()
        self.active_websocket_connections[session_id] = websocket
        # Track that this session has established a WebSocket connection
        self.established_websocket_sessions.add(session_id)
        print(f"Successfully connected session {session_id}")  # Debug line
        return True

    async def disconnect_websocket(self, session_id: str):
        if session_id in self.active_websocket_connections:
            del self.active_websocket_connections[session_id]
            # Don't remove from established_websocket_sessions as we need this for cleanup

    async def send_websocket_message(self, message: str, session_id: str):
        if session_id in self.active_websocket_connections:
            await self.active_websocket_connections[session_id].send_text(message)

    def authorize_upload_session(self, session_id: str):
        self.authorized_upload_sessions.add(session_id)
        print(f"Authorized new session: {session_id}")  # Debug line

websocket_manager = WebSocketConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_instance = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_instance)
    yield
    await redis_instance.close()

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://0.0.0.0:9000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add this helper function
def get_rate_limit_dependency():
    if "pytest" not in sys.modules:
        return [Depends(RateLimiter(times=10, seconds=60))]
    return []

# Add database configuration
DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Replace declarative_base() with a class that inherits from DeclarativeBase
class Base(DeclarativeBase):
    pass

# Add File model
class PDFFileUpload(Base):
    __tablename__ = "pdf_file_uploads"

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String)
    saved_filename = Column(String, unique=True)
    file_size = Column(Integer)
    upload_datetime = Column(DateTime, default=lambda: datetime.now(UTC))
    session_id = Column(String)
    content_type = Column(String)

# Create tables
Base.metadata.create_all(bind=engine)

# Add dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Add new helper function for file cleanup
async def cleanup_session_pdf_files(session_id: str, db: Session):
    # Get all files for this session
    files = db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).all()
    
    # Delete each file
    for file in files:
        file_path = UPLOAD_DIR / file.saved_filename
        try:
            if file_path.exists():
                file_path.unlink()  # Delete the file
            db.delete(file)  # Remove database entry
        except Exception as e:
            print(f"Error deleting file {file.saved_filename}: {e}")
    
    db.commit()

@app.post("/uploadfiles/", dependencies=get_rate_limit_dependency())
async def create_upload_files(
    files: Annotated[list[UploadFile], File(description="Multiple files as UploadFile")],
    db: Session = Depends(get_db),
    status_code=status.HTTP_201_CREATED,
):
    saved_files = []
    errors = []
    session_id = str(uuid.uuid4())  # Move this up since we'll use it for all files
    
    for file in files:
        try:
            if not file.filename:
                raise FileUploadError(file.filename, "Filename is missing")

            # Read file content
            try:
                contents = await file.read()
            except Exception as e:
                raise FileUploadError(file.filename, f"Failed to read file: {str(e)}")

            # Check file size
            file_size = len(contents)
            if file_size > MAX_FILE_SIZE:
                raise FileSizeError(
                    file.filename,
                    f"File size {file_size / (1024 * 1024):.2f}MB exceeds the limit of 30MB"
                )
            
            # Check file extension and MIME type
            if not file.filename.endswith('.pdf') or file.content_type != 'application/pdf':
                raise FileTypeError(
                    file.filename,
                    f"Invalid file type. Only PDF files are allowed (got {file.content_type})"
                )
            
            # Generate and save file with unique name
            original_name = Path(file.filename).stem
            file_extension = Path(file.filename).suffix
            unique_filename = f"{original_name}_{uuid.uuid4()}{file_extension}"
            file_path = UPLOAD_DIR / unique_filename
            
            try:
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(contents)
            except IOError as e:
                raise FileUploadError(file.filename, f"Failed to save file: {str(e)}")
            
            # After successful file save, store metadata in database
            file_upload = PDFFileUpload(
                original_filename=file.filename,
                saved_filename=unique_filename,
                file_size=file_size,
                session_id=session_id,
                content_type=file.content_type
            )
            db.add(file_upload)
            db.commit()
            
            saved_files.append({
                "original_name": file.filename,
                "saved_name": unique_filename
            })
                
        except (FileUploadError, FileSizeError, FileTypeError) as e:
            errors.append({
                "filename": e.filename,
                "error": e.message
            })
        except Exception as e:
            errors.append({
                "filename": getattr(file, 'filename', 'Unknown'),
                "error": f"Unexpected error: {str(e)}"
            })
            
    response = {"files": saved_files}
    if errors:
        response["errors"] = errors
        
    if not saved_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "No files were successfully uploaded",
                "errors": errors
            }
        )
        
    if saved_files:
        # Authorize this session for WebSocket connections
        websocket_manager.authorize_upload_session(session_id)
        # Add session_id to the response
        response["session_id"] = session_id

    return response


@app.get("/")
async def main():
    content = """
<body>
<form action="/uploadfiles/" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)


@app.websocket("/ws/{session_id}")
async def pdf_qa_websocket_endpoint(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)):
    try:
        # Attempt to connect (will fail if session is not authorized)
        is_connected = await websocket_manager.connect_websocket(websocket, session_id)
        
        if not is_connected:
            return

        while True:
            # Receive question from client
            question = await websocket.receive_text()
            
            # For now, return a constant response
            response = "This is a placeholder response. The actual PDF-based Q&A will be implemented later."
            
            # Send response back to client
            await websocket_manager.send_websocket_message(response, session_id)
            
    except WebSocketDisconnect:
        await websocket_manager.disconnect_websocket(session_id)
        # Clean up files only if this session had established a connection
        if session_id in websocket_manager.established_websocket_sessions:
            await cleanup_session_pdf_files(session_id, db)
            websocket_manager.established_websocket_sessions.remove(session_id)
    finally:
        # Ensure we clean up the connection if anything goes wrong
        await websocket_manager.disconnect_websocket(session_id)