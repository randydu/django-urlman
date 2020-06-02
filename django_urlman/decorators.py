""" public decortators """

import functools

from .urlman import _APIWrapper, _urls
from . import marker


def _wrap(func, is_url, **kwargs):
    wrp = _APIWrapper(func, is_url, **kwargs)
    _urls.append(wrp)

    marker.binding(wrp, func, decorator=url if is_url else api)
    return wrp


def _api(func=None, is_url=False, **kwargs):
    if callable(func) or isinstance(func, classmethod) or \
            isinstance(func, staticmethod):
        # decorator without parameters, or called directly with api(f)
        return _wrap(func, is_url, **kwargs)

    # decorator with parameters
    def wrap(func):
        return _wrap(func, is_url, **kwargs)
    return wrap


api = functools.partial(_api, is_url=False)
url = functools.partial(_api, is_url=True)

# method decorators
# ref: @api(methods=['GET','HEAD'])
#
#
#    @get : only support method GET
#
#    @GET
#    @api
#    def foo():pass
#
#    @GET
#    @HEAD
#    @api
#    def bar():pass
#
#    is equal to:
#
#    @api(methods = ['GET', 'HEAD'])
#    def bar():pass
#


def _add_method(func, *, method):
    if not isinstance(func, _APIWrapper):
        raise ValueError(
            'method decorator should be applied on top of @api/@url!')

    if isinstance(method, str):
        func.methods = {*func.methods, method}
    else:
        func.methods = {*func.methods, *method}

    return func


GET = functools.partial(_add_method, method='GET')
POST = functools.partial(_add_method, method='POST')
PUT = functools.partial(_add_method, method='PUT')
HEAD = functools.partial(_add_method, method='HEAD')
DELETE = functools.partial(_add_method, method='DELETE')
PATCH = functools.partial(_add_method, method='PATCH')
CONNECT = functools.partial(_add_method, method='CONNECT')
OPTIONS = functools.partial(_add_method, method='OPTIONS')
TRACE = functools.partial(_add_method, method='TRACE')

# macros
READ = functools.partial(_add_method, method=('GET', 'HEAD'))
WRITE = functools.partial(_add_method, method=('POST', 'PUT', 'PATCH'))
