from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, DateTime
from ..database import Base


class PDFFileUpload(Base):
    """SQLAlchemy model representing uploaded PDF files in the system.

    This model stores metadata about uploaded PDF files including original filename,
    storage location, size, and upload details.

    Attributes:
        id (int): Primary key identifier for the upload record
        original_filename (str): Original name of the uploaded file
        saved_filename (str): Unique filename used to store the file in the system
        file_size (int): Size of the file in bytes
        upload_datetime (datetime): Timestamp when the file was uploaded (in UTC)
        session_id (str): Identifier for the upload session
        content_type (str): MIME type of the uploaded file
    """

    __tablename__ = "pdf_file_uploads"

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String)
    saved_filename = Column(String, unique=True)
    file_size = Column(Integer)
    upload_datetime = Column(DateTime, default=lambda: datetime.now(UTC))
    session_id = Column(String)
    content_type = Column(String)
