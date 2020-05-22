"""
URL Manager for Django
"""

__version__ = "0.2.0"
__license__ = "MIT"
__author__ = "Randy Du <randydu@gmail.com>"

from .urlman import mount, url, api

def _dump_urls():
    """ dump internal urls (internal) """
    from .urlman import _urls
    print(*_urls)