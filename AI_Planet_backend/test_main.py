from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect
from pathlib import Path
import pytest
from main import app, manager, UPLOAD_DIR, Session
import os
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis
import pytest_asyncio
from sqlalchemy.orm import Session

client = TestClient(app)

@pytest_asyncio.fixture(autouse=True)
async def setup_and_cleanup():
    # Setup: Initialize Redis and FastAPILimiter
    redis_instance = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_instance)
    
    # Create uploads directory if it doesn't exist
    UPLOAD_DIR.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup
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

def test_upload_multiple_pdfs(sample_pdf):
    """Test uploading multiple PDF files"""
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
async def test_websocket_unauthorized():
    """Test websocket connection with unauthorized session"""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/invalid-session-id") as websocket:
            # The connection should be closed by the server
            websocket.receive_text()

@pytest.mark.asyncio
async def test_websocket_authorized(sample_pdf):
    """Test websocket connection with authorized session"""
    # First upload a file to get a valid session_id
    with open(sample_pdf, "rb") as f:
        files = {"files": ("test.pdf", f, "application/pdf")}
        response = client.post("/uploadfiles/", files=files)
    
    session_id = response.json()["session_id"]
    
    # Test WebSocket connection with valid session_id
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        # Send a test question
        websocket.send_text("Test question")
        
        # Receive response
        response = websocket.receive_text()
        assert "placeholder response" in response

def test_rate_limiting():
    """Test rate limiting on upload endpoint"""
    # Make 11 requests (more than the 10 per minute limit)
    for _ in range(11):
        response = client.post("/uploadfiles/")
    
    # The last request should return 422 since we're not sending any files
    assert response.status_code == 422 