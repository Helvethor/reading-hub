class ImportFailure(Exception):
    def __init__(self, message, code="failed"):
        super().__init__(message)
        self.code = code


class LimitExceeded(ImportFailure):
    def __init__(self, message):
        super().__init__(message, "limit")
