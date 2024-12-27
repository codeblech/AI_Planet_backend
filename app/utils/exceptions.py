class FileUploadError(Exception):
    def __init__(self, filename: str, message: str):
        self.filename = filename
        self.message = message
        super().__init__(self.message)

class FileSizeError(FileUploadError):
    pass

class FileTypeError(FileUploadError):
    pass 