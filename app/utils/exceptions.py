class FileUploadError(Exception):
    """Base exception class for file upload related errors.

    Args:
        filename (str): Name of the file that caused the error
        message (str): Detailed error message
    """
    def __init__(self, filename: str, message: str):
        self.filename = filename
        self.message = message
        super().__init__(self.message)

class FileSizeError(FileUploadError):
    """Exception raised when an uploaded file exceeds the maximum allowed size."""
    pass

class FileTypeError(FileUploadError):
    """Exception raised when an uploaded file has an invalid or unsupported file type."""
    pass 