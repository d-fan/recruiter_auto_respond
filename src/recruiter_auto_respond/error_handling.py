
import httpx
from googleapiclient.errors import HttpError


def is_transient_error(exception: BaseException) -> bool:
    """Predicate to determine if an exception is transient and should be retried.

    Handles:
    - httpx status errors (5xx, 429) and request errors (timeout, connection).
    - Google API HttpErrors (5xx, 429).
    """
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exception, httpx.RequestError):
        return True

    if isinstance(exception, HttpError):
        # googleapiclient.errors.HttpError has status_code or resp.status
        status_code = getattr(exception, "status_code", None)
        if status_code is None:
            status_code = getattr(exception.resp, "status", None)
        return status_code in (429, 500, 502, 503, 504)

    return False
