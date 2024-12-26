from typing import Annotated
from fastapi import FastAPI, File, UploadFile, status, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import os
from pathlib import Path
import uuid
import aiofiles

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
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add error handler middleware
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred"}
        )

@app.post("/uploadfiles/", dependencies=[Depends(RateLimiter(times=2, seconds=60))])
async def create_upload_files(
    files: Annotated[list[UploadFile], File(description="Multiple files as UploadFile")],
    status_code=status.HTTP_201_CREATED,
):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were provided"
        )

    saved_files = []
    errors = []
    
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