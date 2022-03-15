class NoResultException(RuntimeError):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class InvalidExternalServiceStatusException(RuntimeError):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class InvalidExternalServiceResponseException(RuntimeError):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
