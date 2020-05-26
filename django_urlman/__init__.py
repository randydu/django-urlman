"""
URL Manager for Django
"""

__version__ = "0.2.0"
__license__ = "MIT"
__author__ = "Randy Du <randydu@gmail.com>"

from .urlman import mount, url, api, map_module, APIResult, HEAD, GET, POST, PUT, PATCH, DELETE, CONNECT, OPTIONS, TRACE, READ, WRITE

def _dump_urls():
    """ dump internal urls (internal) """
    from .urlman import _urls

    print('*** Dump of all registered urls ***\n')
    
    for i, url in enumerate(_urls):
        print(f'[{i}] {url.site_url}\n')
