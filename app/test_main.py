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

@pytest.mark.asyncio
async def test_websocket_connection_authorized(sample_pdf):
    """Test websocket connection with authorized session"""
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    await asyncio.sleep(0.1)
    
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        websocket.send_text("Test question")
        response = websocket.receive_text()
        assert "placeholder response" in response

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

