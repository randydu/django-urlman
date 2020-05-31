"""
URL Manager for Django
"""

__version__ = "0.3.0"
__license__ = "MIT"
__author__ = "Randy Du <randydu@gmail.com>"

from .urlman import (mount, url, api, app_path, module_path, APIResult,
                     HEAD, GET, POST, PUT, PATCH, DELETE, CONNECT, OPTIONS,
                     TRACE, READ, WRITE, get_wrapper, _dump_urls)
