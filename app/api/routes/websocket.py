from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from sqlalchemy.orm import Session
import sys
from ...database import get_db
from ...services.websocket_manager import websocket_manager
from fastapi_limiter.depends import WebSocketRateLimiter
from pathlib import Path
from ...models.pdf_upload import PDFFileUpload
from ...config import UPLOAD_DIR
from ...services.pdf_processor import PDFProcessor

router = APIRouter()


async def cleanup_session_pdf_files(session_id: str, db: Session):
    """
    Clean up PDF files associated with a specific session.

    Args:
        session_id (str): The unique identifier for the session
        db (Session): SQLAlchemy database session

    This function removes both the physical PDF files from storage
    and their corresponding database entries.
    """
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
async def pdf_qa_websocket_endpoint(
    websocket: WebSocket, session_id: str, db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for PDF question-answering functionality.

    Args:
        websocket (WebSocket): The WebSocket connection instance
        session_id (str): Unique identifier for the client session
        db (Session): SQLAlchemy database session dependency

    This endpoint handles:
        - WebSocket connection management
        - PDF file processing for the session
        - Question-answering interactions
        - Rate limiting (except in test environment)
        - Cleanup of resources on disconnect

    Raises:
        WebSocketDisconnect: When the client disconnects from the WebSocket
    """
    try:
        is_connected = await websocket_manager.connect_websocket(websocket, session_id)

        if not is_connected:
            return

        # Initialize PDF processor
        pdf_processor = PDFProcessor()

        # Get PDF files for this session
        pdf_files = (
            db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).all()
        )
        pdf_paths = [UPLOAD_DIR / file.saved_filename for file in pdf_files]

        # Process PDFs
        await pdf_processor.process_pdfs(session_id, pdf_paths)

        # Only apply rate limiting if not in test environment
        if "pytest" not in sys.modules:
            ratelimit = WebSocketRateLimiter(times=10, seconds=60)

        try:
            while True:
                question = await websocket.receive_text()

                # Apply rate limiting only if not in test environment
                if "pytest" not in sys.modules:
                    await ratelimit(websocket, context_key=session_id)

                # Get answer from PDF processor
                response = await pdf_processor.get_answer(session_id, question)
                await websocket_manager.send_websocket_message(response, session_id)

        except WebSocketDisconnect:
            raise

    except WebSocketDisconnect:
        await websocket_manager.disconnect_websocket(session_id)
        if session_id in websocket_manager.established_websocket_sessions:
            # Clean up PDF processor resources
            pdf_processor.cleanup_session(session_id)
            # Clean up files
            await cleanup_session_pdf_files(session_id, db)
            websocket_manager.established_websocket_sessions.remove(session_id)
            websocket_manager.authorized_upload_sessions.remove(session_id)
    finally:
        await websocket_manager.disconnect_websocket(session_id)
