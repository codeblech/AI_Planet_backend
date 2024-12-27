from pathlib import Path

# File upload settings
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB in bytes
UPLOAD_DIR = Path("uploads") # For uploaded pdf files
UPLOAD_DIR.mkdir(exist_ok=True)

# Database settings
DATABASE_URL = "sqlite:///./sql_app.db"

# CORS settings
CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://0.0.0.0:9000",
]