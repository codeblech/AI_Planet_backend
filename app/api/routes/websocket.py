from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from sqlalchemy.orm import Session
import sys
from ...database import get_db
from ...services.websocket_manager import websocket_manager
from fastapi_limiter.depends import WebSocketRateLimiter
from pathlib import Path
from ...models.pdf_upload import PDFFileUpload
from ...config import UPLOAD_DIR

router = APIRouter()

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


@router.websocket("/ws/{session_id}")
async def pdf_qa_websocket_endpoint(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)):
    try:
        is_connected = await websocket_manager.connect_websocket(websocket, session_id)
        
        if not is_connected:
            return

        # Only apply rate limiting if not in test environment
        if "pytest" not in sys.modules:
            ratelimit = WebSocketRateLimiter(times=10, seconds=60)  # 10 messages per minute
        
        try:
            while True:
                question = await websocket.receive_text()
                
                # Apply rate limiting only if not in test environment
                if "pytest" not in sys.modules:
                    await ratelimit(websocket, context_key=session_id)
                
                response = "This is a placeholder response. The actual PDF-based Q&A will be implemented later."
                await websocket_manager.send_websocket_message(response, session_id)
        except WebSocketDisconnect:
            raise  # Re-raise to be caught by outer try block
            
    except WebSocketDisconnect:
        await websocket_manager.disconnect_websocket(session_id)
        # Clean up files only if this session had established a connection
        if session_id in websocket_manager.established_websocket_sessions:
            await cleanup_session_pdf_files(session_id, db)
            websocket_manager.established_websocket_sessions.remove(session_id)
            websocket_manager.authorized_upload_sessions.remove(session_id)
    finally:
        await websocket_manager.disconnect_websocket(session_id)