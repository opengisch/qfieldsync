class QFieldSyncError(Exception):
    pass


class CannotUploadFileError(QFieldSyncError):
    """Raised when the current user is not allowed to upload a file to a QFieldCloud project."""
