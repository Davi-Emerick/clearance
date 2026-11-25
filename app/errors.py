class ClearanceError(Exception):
    """A desk rule refused the request, or the record is missing."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
