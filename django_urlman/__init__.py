"""
URL Manager for Django
"""

__version__ = "0.6.0"
__license__ = "MIT"
__author__ = "Randy Du <randydu@gmail.com>"

from .urlman import (mount, app_path, module_path, APIResult,
                     get_wrapper, _dump_urls)

from .decorators import (url, api, HEAD, GET, POST, PUT, PATCH, DELETE,
                         CONNECT, OPTIONS, TRACE, READ, WRITE)

from .marker import mark
