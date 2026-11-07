"""ETL layer: extract health data from Zepp, transform, load into SQLite."""

__version__ = "0.3.0"

from .client import ZeppClient
from .exceptions import ZeppAPIError, ZeppAuthError, ZeppDecodeError

__all__ = ["ZeppClient", "ZeppAuthError", "ZeppAPIError", "ZeppDecodeError", "__version__"]
