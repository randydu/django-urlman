import sys
import importlib
import inspect
import traceback
import functools
import json

from django.urls import path, re_path
from django.http.response import HttpResponseBase, JsonResponse, HttpResponseNotAllowed, HttpResponseBadRequest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls.converters import get_converters

# make sure built-in converters are registered.
from . import converters

_urls = []
_module_maps = {} # mapping module to a url

def _geturl(prj, apps, pkg, module, fname, param_url, *, module_maps = None, app_url = None):
    """ deduce url from meta info """
    module_maps = module_maps or _module_maps
    segs = module.split('.')
    app = pkg if pkg != '' else segs[0]
    anchor = apps.get(app, app) if app != prj else ''

    if app_url is None:
        parts = segs[1:]
        try:
            # exact match first
            parts = module_maps[module].split('/')
        except:
            # searching partial matching
            for i in sorted(module_maps, key=lambda x: len(x), reverse=True):
                if module.startswith(i):
                    leftover = module[len(i):]
                    if len(leftover) == 0:
                        parts = module_maps[i].split('/')
                        break
                    elif leftover[0] == '.':
                        parts = module_maps[i].split('/') + leftover[1:].split('.')
                        break
        
        while parts and parts[0] == '':
            parts = parts[1:]

        if fname:
            parts.append(fname)
    else:
        # app-wide url is specified
        parts = app_url.strip(' /').split('/')

    if anchor == '':
        url = '/'.join(parts)
    else:
        url = '/'.join([anchor.rstrip('/'),] + parts)
    
    url += param_url
        
    # force trailing slash to avoid potential django route resolving issue.
    if not url.endswith('/'):
        url+='/'
    return url



def _get_all_paths(prj:str, apps: dict):
    """ get all all registered urls """
    
    # resolve paths
    paths = []
    #for pkg, module, api, handler in _urls:
    for x in _urls:
        if x.site_url is None:
            # site_url not specified, resolve it... 
            m = sys.modules[x.f.__module__]
            x.site_url = _geturl(prj, apps, m.__package__, x.f.__module__, x.func_name, x.param_url, app_url=x.url)
        
        xpath = re_path if x.has_optional_param else path
        paths.append(xpath(x.site_url, x, name = x.url_name))

    return paths

def mount(apps: dict = {}, *, urlconf = None, only_me = False):
    import django.conf

    urlconf = urlconf or django.conf.settings.ROOT_URLCONF
    mroot = importlib.import_module(urlconf)
    prj = mroot.__package__

    # Loading apps will trigger registration of all app urls/apis.
    #
    # If an app does not appear explicitly in "apps" dictionary, it must be imported somewhere 
    # in order to register its apis.
    #
    # When app is in "apps" dictionary, it can specify the mounting point in the site / project,
    # otherwise its mounting point will be the app's package name. (<package_name>/)
    if apps:
        if not isinstance(apps, dict):
            raise ValueError("apps must be a dictionary!")

        # import apps
        for app in apps:
            if app != prj: # don't load project
                m = importlib.import_module(app)
                if hasattr(m, '__path__'):
                    import pkgutil
                    # package, loading all modules except special files (setup.py)
                    for _, name, _ in pkgutil.iter_modules(m.__path__):
                        if name not in ('setup'):
                            importlib.import_module('.'+name, package=app)

    
    if only_me:
        mroot.urlpatterns = _get_all_paths(prj, apps)
    else:
        mroot.urlpatterns += _get_all_paths(prj, apps)


class _MyJSONEncoder(DjangoJSONEncoder):
    enable_all_fields = False # include private fields?
    include_cls_id = False # include '_cls_' field indicating which class generates the data

    def default(self, obj):
        try:
            return super().default(obj)
        except:
            # To minimize serialized data size, only instantiated fields are saved and the fields defined in class are ignored.
            r = dict(obj.__dict__) if self.enable_all_fields else { k:v for k,v in obj.__dict__.items() if not k.startswith('_') }
            if self.include_cls_id:
                r['_cls_'] = type(obj).__name__
            return r

class _APIWrapper(object):
    def __init__(self, f, is_url = False, **kwargs):
        self.f = f
        self.func_name = kwargs.get('func_name', f.__name__ if hasattr(f, '__name__') else f.__class__.__name__)
        self.url_name = kwargs.get('name', f.__module__ + '.' + self.func_name)
        self.url = kwargs.get('url', None) # app-wide url
        self.site_url = kwargs.get('site_url', None) # site-wide url
        self.methods = {*[x.upper() for x in kwargs.get('methods', [])]}

        self._is_url = is_url

        self.defaults = {} # param's default value
        self.types = {}    # param's type annotation
        self.pos_call = []  # pass param by position
        self.pos_only = []  # position only param
        self.param_autos = kwargs.get('param_autos', ()) # param should be retrieved from body, query

        params = inspect.signature(self.f).parameters

        param_types = kwargs.get('param_types',{})
        
        self.names = [*params]
        if is_url:
            # skip first parameter (request)
            self.names = self.names[1:]

        for i, x in enumerate(self.names):
            param = params[x]

            if param.kind == inspect.Parameter.POSITIONAL_ONLY or param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                # call by position
                assert len(self.pos_call) == i
                self.pos_call.append(x)

                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    self.pos_only.append(x)

            v = param.default

            if v == inspect._empty:
                # no default value
                cls = param.annotation
                if cls != inspect._empty:
                    self.types[x] = cls
                else:
                    # decorator provided type annotation via 'param_types'
                    if x in param_types:
                        self.types[x] = param_types[x]
            else:
                # has default value
                self.defaults[x] = v
                self.types[x] = type(v)

    def _invoke(self, req, *args, **kwargs):
        if self.pos_call:
            # extract call_by_pos params 
            myargs = []
            for x in self.pos_call:
                myargs.append(kwargs[x])
                kwargs.pop(x)
            myargs += args

            if self._is_url:
                if kwargs:
                    r = self.f(req, *myargs, **kwargs)
                else:
                    r = self.f(req, *myargs)
            else:
                if kwargs:
                    r = self.f(*myargs, **kwargs)
                else:
                    r = self.f(*myargs)
        else:
            if self._is_url:
                r = self.f(req, *args, **kwargs)
            else:
                r = self.f(*args, **kwargs)
        
        return r

    def _type_cast(self, x,v):
        # cast param x to registered type
        if x in self.types:
            typ = self.types[x]

            if not isinstance(v, typ):
                try:
                    v = get_converters()[typ.__name__].to_python(v)
                except KeyError:
                    # no matched converter, fall back to type constructor
                    try:
                        v = typ(v)
                    except:
                        pass
        return v



    def __call__(self, req, *args, **kwargs):
        try:
            # check the method permission
            if self.methods and req.method.upper() not in self.methods:
                return HttpResponseNotAllowed(self.methods)

            if self.has_optional_param or self.param_autos:
                # re_path() does not cope with type conversion so we have to do it manually
                # non-empty param_autos means some params needed to be retrieved from other parts of request
                mykwargs = { **kwargs }

                for x in self.names:
                    if x in mykwargs:
                        # param provided by caller
                        mykwargs[x] = self._type_cast(x, mykwargs[x])
                    else:
                        # param not provided by caller
                        found = False
                        if x in self.param_autos:
                            if req.content_type == 'application/json':
                                content = json.loads(req.body)
                                if x in content:
                                    v = content[x]
                                    found = True
                            else:
                                # search in POST which is parsed from body.
                                try:
                                    v = req.POST[x]
                                    found = True
                                except:
                                    pass

                                # search in GET which is parsed from query-string.
                                try:
                                    v = req.GET[x]
                                    found = True
                                except:
                                    pass

                                # search in cookie
                                try:
                                    # v = req.get_signed_cookie(x)
                                    v = req.COOKIES[x]
                                    found = True
                                except:
                                    pass

                                # search session
                                if hasattr(req, 'session'):
                                    try:
                                        v = req.session[x]
                                        found = True
                                    except:
                                        pass

                        if not found:
                            if x in self.defaults:
                                mykwargs[x] = self.defaults[x]
                                found = True
                        else:
                            mykwargs[x] = self._type_cast(x, v)

                        if not found and not args: # todo: check positional params in args
                            return HttpResponseBadRequest('parameter (%s) not found' % x)

                r = self._invoke(req, *args, **mykwargs)

            else:
                # path() has done type conversion so just pass them directly to wrapped function
                r = self._invoke(req, *args, **kwargs)

            if isinstance(r, HttpResponseBase):
                return r

            return JsonResponse({
                    'error': None,
                    'result': r, 
                }, safe = False, encoder = _MyJSONEncoder)
        except:
            ex = sys.exc_info()
            return JsonResponse({
                    'error': ex[0].__name__,
                    'stack': traceback.format_exception(*ex),

                    'result': None, 
                }, safe = False, encoder = _MyJSONEncoder)


    @property
    def param_url(self):
        # param-based url.
        # '' if no param; it has the leading slash if needed, no trailing slash. 
        if self.defaults:
            # has optional parameter, use re_path()
            def get_one_url(x):
                regex = '[^/]+'
                
                if x in self.types:
                    typ = self.types[x].__name__ 
                    try:
                        regex = get_converters()[typ].regex
                    except KeyError:
                        # unregistered converter 
                        pass

                if x in self.defaults:
                    # x is optional
                    return f"(?:/(?P<{x}>{regex}))?" if x in self.pos_only else f"(?:/{x}/(?P<{x}>{regex}))?"
                else:
                    # x is not optional
                    return f"/(?P<{x}>{regex})" if x in self.pos_only else f"/{x}/(?P<{x}>{regex})"

        else:
            # no optional parameter, use path()
            def get_one_url(x):
                try:
                    typ = self.types[x].__name__ + ':'
                except KeyError:
                    typ = ''

                return f"/<{typ}{x}>" if x in self.pos_only else f"/{x}/<{typ}{x}>"

        return ''.join([ get_one_url(x) for x in self.names if x not in self.param_autos ])

    @property
    def has_optional_param(self):
        return self.defaults != {}

def _wrap(f, is_url, **kwargs):
    _urls.append(_APIWrapper(f, is_url, **kwargs))
    return f


def _api(f = None, is_url = False, **kwargs):
    if callable(f):
        # decorator without parameters, or called directly with api(f)
        return _wrap(f, is_url, **kwargs)
    else:
        # decorator with parameters
        def wrap(func):
            return _wrap(func, is_url, **kwargs)
        return wrap

api = functools.partial(_api, is_url = False)
url = functools.partial(_api, is_url = True)


def map_module(module, url):
    """ maps module to a url """
    if inspect.ismodule(module):
        nm = module.__name__
    elif isinstance(module, str):
        nm = module
    else:
        raise ValueError("'module' must be either a module or a module name")

    _module_maps[nm] = url


def _get_wrapper(f):
    """ [INTERNAL] get the wrapper of a wrapped function """
    for x in _urls:
        if x.f is f:
            return x
    
    raise ValueError('f is not wrapped by @api/@url')

class APIResult:
    '''utility to retrieve result of api from response'''
    def __init__(self, response):
        self.r = json.loads(response.content)
    @property
    def error(self):
        return self.r['error']
    @property
    def stack(self):
        return self.r.get('stack', None)
    @property
    def result(self):
        return self.r['result']

# method decorators
# ref: @api(methods=['GET','HEAD'])
    '''@get : only support method GET
    
        @GET
        @api
        def foo():pass

        @GET
        @HEAD
        @api
        def bar():pass

        is equal to:

        @api(methods = ['GET', 'HEAD'])
        def bar():pass
    '''

def _add_method(f, *, method):
    wrp = _get_wrapper(f)
    if isinstance(method, str):
        wrp.methods = { *wrp.methods, method}
    else:
        wrp.methods = { *wrp.methods, *method}
    return f

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
READ = functools.partial(_add_method, method = ('GET', 'HEAD'))
WRITE = functools.partial(_add_method, method = ('POST', 'PUT', 'PATCH'))