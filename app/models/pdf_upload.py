from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, DateTime
from ..database import Base

class PDFFileUpload(Base):
    __tablename__ = "pdf_file_uploads"

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String)
    saved_filename = Column(String, unique=True)
    file_size = Column(Integer)
    upload_datetime = Column(DateTime, default=lambda: datetime.now(UTC))
    session_id = Column(String)
    content_type = Column(String) 