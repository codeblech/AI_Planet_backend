from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect
from pathlib import Path
import pytest
from app.api.routes.upload import UPLOAD_DIR
from app.api.routes.websocket import websocket_manager
from app.database import SessionLocal, Base, engine
from app.models.pdf_upload import PDFFileUpload
from app.main import app
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis
import pytest_asyncio
import shutil
import asyncio
import os

client = TestClient(app)

@pytest_asyncio.fixture(autouse=True)
async def setup_and_cleanup():
    # Setup: Initialize Redis and FastAPILimiter
    redis_instance = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_instance)
    
    # Clear any existing rate limits
    await redis_instance.flushall()
    
    # Create uploads directory if it doesn't exist
    UPLOAD_DIR.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup
    await redis_instance.flushall()
    await redis_instance.aclose()
    # Remove test files
    for file in UPLOAD_DIR.glob("*"):
        try:
            file.unlink()
        except Exception:
            pass

@pytest.fixture
def sample_pdf():
    # Create a small PDF-like file for testing
    pdf_content = b"%PDF-1.4\n%Test PDF content"
    test_pdf = Path("test_sample.pdf")
    test_pdf.write_bytes(pdf_content)
    yield test_pdf
    # Cleanup
    test_pdf.unlink(missing_ok=True)

def test_read_main():
    """Test the root endpoint returns HTML form"""
    response = client.get("/")
    assert response.status_code == 200
    assert "multipart/form-data" in response.text
    assert '<form action="/uploadfiles/"' in response.text

def test_upload_no_file():
    """Test uploading with no files"""
    response = client.post("/uploadfiles/")
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "missing"
    assert response.json()["detail"][0]["loc"] == ["body", "files"]

def test_upload_invalid_file_type(sample_pdf):
    """Test uploading non-PDF file"""
    # Create a fake text file
    with open("test.txt", "w") as f:
        f.write("This is not a PDF")
    
    with open("test.txt", "rb") as f:
        files = {"files": ("test.txt", f, "text/plain")}
        response = client.post("/uploadfiles/", files=files)
    
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]["errors"][0]["error"]
    
    # Cleanup
    os.remove("test.txt")

def test_upload_valid_pdf(sample_pdf):
    """Test uploading valid PDF file"""
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    assert response.status_code == 200
    assert "files" in response.json()
    assert "session_id" in response.json()
    assert len(response.json()["files"]) == 1
    assert response.json()["files"][0]["original_name"] == "test.pdf"

def test_multiple_pdf_upload(sample_pdf):
    """Test uploading multiple PDF files simultaneously"""
    with open(sample_pdf, "rb") as f1, open(sample_pdf, "rb") as f2:
        files = [
            ("files", ("test1.pdf", f1, "application/pdf")),
            ("files", ("test2.pdf", f2, "application/pdf"))
        ]
        response = client.post("/uploadfiles/", files=files)
    
    assert response.status_code == 200
    assert len(response.json()["files"]) == 2
    assert "session_id" in response.json()

@pytest.mark.asyncio
async def test_websocket_connection_unauthorized():
    """Test websocket connection with unauthorized session"""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/invalid-session-id") as websocket:
            websocket.receive_text()

@pytest.mark.asyncio
async def test_websocket_connection_authorized(sample_pdf):
    """Test websocket connection with authorized session"""
    # First upload a file to get a valid session_id
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    
    # Add delay to ensure session is properly registered
    await asyncio.sleep(0.1)
    
    # Test WebSocket connection with valid session_id
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        # Use sync methods instead of async
        websocket.send_text("Test question")
        response = websocket.receive_text()
        assert "placeholder response" in response

@pytest.fixture(scope="function")
def test_db():
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)
    
    # Create test database tables
    Base.metadata.create_all(bind=engine)
    
    # Get a test database session
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up the database after each test
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def cleanup_uploads():
    # Setup: ensure upload directory exists
    UPLOAD_DIR.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup: remove all files in upload directory
    shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(exist_ok=True)

def test_pdf_database_entry(test_db, sample_pdf, cleanup_uploads):
    """Test database entry creation when uploading PDF files"""
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    
    # Check database entry
    db_file = test_db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).first()
    assert db_file is not None
    assert db_file.original_filename == "test.pdf"
    assert db_file.content_type == "application/pdf"
    assert db_file.session_id == session_id

def test_pdf_cleanup_after_websocket_disconnect(test_db, sample_pdf, cleanup_uploads):
    """Test that PDF files are cleaned up after WebSocket disconnection"""
    # First upload a file
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    saved_filename = response.json()["files"][0]["saved_name"]
    
    # Verify file exists in database and filesystem
    assert test_db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).count() == 1
    assert (UPLOAD_DIR / saved_filename).exists()
    
    # Connect and disconnect WebSocket
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        websocket.send_text("Test question")
        response = websocket.receive_text()
        assert "placeholder response" in response
    
    # Verify file is deleted from both database and filesystem
    assert test_db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).count() == 0
    assert not (UPLOAD_DIR / saved_filename).exists()

def test_pdf_files_persist_without_websocket(test_db, sample_pdf, cleanup_uploads):
    """Test that PDF files remain when no WebSocket connection is made"""
    # Upload a file
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    saved_filename = response.json()["files"][0]["saved_name"]
    
    # Verify file exists
    assert test_db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).count() == 1
    assert (UPLOAD_DIR / saved_filename).exists()
    
    # Don't connect WebSocket
    # Wait a moment to ensure no automatic cleanup
    import time
    time.sleep(1)
    
    # Verify file still exists
    assert test_db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).count() == 1
    assert (UPLOAD_DIR / saved_filename).exists()

@pytest.mark.asyncio
async def test_multiple_pdf_cleanup(test_db, sample_pdf, cleanup_uploads):
    """Test cleanup of multiple PDF files for same session"""
    # Upload multiple files
    with open(sample_pdf, "rb") as f1, open(sample_pdf, "rb") as f2:
        files = [
            ("files", ("test1.pdf", f1, "application/pdf")),
            ("files", ("test2.pdf", f2, "application/pdf"))
        ]
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    saved_filenames = [file["saved_name"] for file in response.json()["files"]]
    
    # Add delay to ensure session is properly registered
    await asyncio.sleep(0.1)
    
    # Verify files exist
    assert test_db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).count() == 2
    for filename in saved_filenames:
        assert (UPLOAD_DIR / filename).exists()
    
    # Connect and disconnect WebSocket
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        # Use sync methods instead of async
        websocket.send_text("Test question")
        response = websocket.receive_text()
    
    # Add delay to ensure cleanup has completed
    await asyncio.sleep(0.1)
    
    # Verify all files are cleaned up
    assert test_db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).count() == 0
    for filename in saved_filenames:
        assert not (UPLOAD_DIR / filename).exists()

def test_pdf_upload_and_websocket_integration(test_db, sample_pdf, cleanup_uploads):
    """Test complete flow of PDF upload and websocket connection"""
    # Upload PDF
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    
    # Check database entry
    db_file = test_db.query(PDFFileUpload).filter(PDFFileUpload.session_id == session_id).first()
    assert db_file is not None
    
    # Verify session is authorized
    assert session_id in websocket_manager.authorized_upload_sessions
    assert session_id not in websocket_manager.established_websocket_sessions

def test_websocket_connection_lifecycle(test_db, sample_pdf, cleanup_uploads):
    """Test WebSocket connection lifecycle states"""
    # Upload a file
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    
    # Verify session is authorized
    assert session_id in websocket_manager.authorized_upload_sessions
    assert session_id not in websocket_manager.established_websocket_sessions
    
    # Connect WebSocket
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        # Verify session is connected
        assert session_id in websocket_manager.established_websocket_sessions
        assert session_id in websocket_manager.active_websocket_connections
    
    # After disconnection, verify session is removed from tracking
    assert session_id not in websocket_manager.active_websocket_connections
    assert session_id not in websocket_manager.established_websocket_sessions 

@pytest.mark.asyncio
async def test_pdf_processing_initialization(test_db, sample_pdf, cleanup_uploads):
    """Test PDF processor initialization with uploaded files"""
    # Upload a PDF
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    
    # Connect WebSocket to trigger PDF processing
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        # The connection itself should trigger PDF processing
        # Send a test message to ensure processing is complete
        websocket.send_text("Is the PDF processed?")
        response = websocket.receive_text()
        assert response is not None

@pytest.mark.asyncio
async def test_pdf_processing_multiple_files(test_db, sample_pdf, cleanup_uploads):
    """Test processing multiple PDFs in the same session"""
    # Upload multiple PDFs
    with open(sample_pdf, "rb") as f1, open(sample_pdf, "rb") as f2:
        files = [
            ("files", ("test1.pdf", f1, "application/pdf")),
            ("files", ("test2.pdf", f2, "application/pdf"))
        ]
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    
    # Connect WebSocket and verify processing
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        websocket.send_text("Test question about multiple PDFs")
        response = websocket.receive_text()
        assert response is not None

@pytest.mark.asyncio
async def test_pdf_processing_error_handling(test_db, cleanup_uploads):
    """Test PDF processor error handling with invalid PDF"""
    # Create an invalid PDF file
    invalid_pdf = Path("invalid.pdf")
    invalid_pdf.write_text("This is not a valid PDF file")
    
    try:
        # Try to upload invalid PDF
        with open(invalid_pdf, "rb") as f:
            files = {"files": ("invalid.pdf", f, "application/pdf")}
            response = client.post("/uploadfiles/", files=files)
        
        session_id = response.json()["session_id"]
        
        # Connect WebSocket and verify error handling
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            websocket.send_text("Test question")
            response = websocket.receive_text()
            assert "error" in response.lower()
    
    finally:
        # Cleanup
        invalid_pdf.unlink(missing_ok=True)

@pytest.mark.asyncio
async def test_pdf_qa_functionality(test_db, sample_pdf, cleanup_uploads):
    """Test question-answering functionality with processed PDFs"""
    # Create a PDF with specific content
    pdf_content = b"%PDF-1.4\nThis is a test document about FastAPI testing."
    test_pdf = Path("test_content.pdf")
    test_pdf.write_bytes(pdf_content)
    
    try:
        # Upload PDF
        with open(test_pdf, "rb") as f:
            files = {"files": ("test_content.pdf", f, "application/pdf")}
            response = client.post("/uploadfiles/", files=files)
        
        session_id = response.json()["session_id"]
        
        # Test Q&A functionality
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Send relevant question
            websocket.send_text("What is this document about?")
            response = websocket.receive_text()
            assert "fastapi" in response.lower() or "test" in response.lower()
            
            # Send irrelevant question
            websocket.send_text("What is the capital of France?")
            response = websocket.receive_text()
            assert "no relevant information" in response.lower() or "cannot answer" in response.lower()
    
    finally:
        # Cleanup
        test_pdf.unlink(missing_ok=True) 