from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from fastapi.responses import HTMLResponse
from typing import Annotated
import uuid
import aiofiles
from pathlib import Path
import sys
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.pdf_upload import PDFFileUpload
from ...utils.exceptions import FileUploadError, FileSizeError, FileTypeError
from ...config import MAX_FILE_SIZE, UPLOAD_DIR
from ...services.websocket_manager import websocket_manager
from fastapi_limiter.depends import RateLimiter

router = APIRouter()

def get_upload_rate_limit_dependency():
    """
    Creates rate limiting dependency for upload endpoints.
    
    Returns:
        list: List of FastAPI dependencies containing rate limiter if not in test environment,
              empty list otherwise.
    """
    if "pytest" not in sys.modules:
        return [Depends(RateLimiter(times=5, seconds=60))]
    return []

@router.post("/uploadfiles/", dependencies=get_upload_rate_limit_dependency())
async def create_upload_files(
    files: Annotated[list[UploadFile], File(description="Multiple files as UploadFile")],
    db: Session = Depends(get_db),
):
    """
    Handle multiple file uploads, storing files and their metadata.

    Args:
        files (list[UploadFile]): List of files to upload
        db (Session): Database session dependency

    Returns:
        dict: Response containing:
            - files (list): Successfully uploaded files with original and saved names
            - errors (list, optional): Any errors that occurred during upload
            - session_id (str): Unique session ID for WebSocket communication

    Raises:
        HTTPException: When no files are successfully uploaded
        FileUploadError: When file upload fails
        FileSizeError: When file size exceeds limit
        FileTypeError: When file type is not PDF

    Example:
        Response format:
        {
            "files": [
                {
                    "original_name": "example.pdf",
                    "saved_name": "example_uuid.pdf"
                }
            ],
            "session_id": "uuid-string",
            "errors": [  # optional
                {
                    "filename": "invalid.txt",
                    "error": "Invalid file type"
                }
            ]
        }
    """
    saved_files = []
    errors = []
    session_id = str(uuid.uuid4())
    
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

@router.get("/")
async def main():
    """
    Render simple HTML upload form for testing.

    Returns:
        HTMLResponse: Basic HTML form for file uploads
    """
    content = """
    <body>
    <form action="/uploadfiles/" enctype="multipart/form-data" method="post">
    <input name="files" type="file" multiple>
    <input type="submit">
    </form>
    </body>
    """
    return HTMLResponse(content=content) 