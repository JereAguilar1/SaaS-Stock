"""Custom exceptions for the SaaS Stock application."""

class SaasError(Exception):
    """Base exception for all application errors."""
    def __init__(self, message="An internal error occurred", status_code=500, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['status'] = 'error'
        return rv

class BusinessLogicError(SaasError):
    """Exception raised for business logic violations."""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__(message, status_code, payload)

class NotFoundError(SaasError):
    """Exception raised when a resource is not found."""
    def __init__(self, message="Resource not found", payload=None):
        super().__init__(message, 404, payload)

class InsufficientStockError(BusinessLogicError):
    """Raised when an operation fails due to lack of stock."""
    def __init__(self, product_name, required, available):
        req_fmt = f"{int(required)}" if required % 1 == 0 else f"{required:.2f}".rstrip('0').rstrip('.')
        avail_fmt = f"{int(available)}" if available % 1 == 0 else f"{available:.2f}".rstrip('0').rstrip('.')
        message = f"Stock insuficiente para {product_name}: se requieren {req_fmt}, disponible {avail_fmt}"
        super().__init__(message, status_code=409)

class UnauthorizedError(SaasError):
    """Raised when a user lacks permission for an action."""
    def __init__(self, message="Unauthorized access"):
        super().__init__(message, 403)
