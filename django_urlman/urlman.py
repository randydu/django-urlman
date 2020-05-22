from django.urls import path

import sys
import importlib
import inspect
import datetime
from django.http.response import HttpResponseBase, JsonResponse

_urls = []

def _geturl(prj, apps, pkg, module, fname, param_url):
    """ deduce url from meta info """
    segs = module.split('.')
    app = pkg if pkg != '' else segs[0]
    anchor = apps.get(app, app) if app != prj else ''

    if anchor == '':
        url = '/'.join(segs[1:] + [fname, ])
    else:
        url = '/'.join([anchor.rstrip('/'),] + segs[1:] + [fname, ])
    
    return url if param_url == '' else '/'.join((url, param_url))



def mount(prj:str, apps: dict = None):
    """ Mount all registered urls """
    if apps is not None:
        if not isinstance(apps, dict):
            raise ValueError("apps must be a dictionary!")

        # import apps
        for app in apps:
            if app != prj: # don't load project
                m = importlib.import_module(app)
                if hasattr(m, '__path__'):
                    import pkgutil
                    # package
                    for _, name, _ in pkgutil.iter_modules(m.__path__):
                        if name not in ('setup'):
                            importlib.import_module('.'+name, package=app)
    
    # resolve paths
    paths = []
    #for pkg, module, api, handler in _urls:
    for x in _urls:
        m = sys.modules[x.__module__]
        url = _geturl(prj, apps, m.__package__, x.__module__, x.__name__, x.param_url if isinstance(x, _APIWrapper) else '')
        
        print('\nurl: %s' % url )

        paths.append(path(url, x))

    return paths



def url(f):
    """ url decorator for function """
    _urls.append(f)
    return f

class _APIWrapper(object):
    def __init__(self, f):
        self.__module__ = f.__module__
        self.__name__ = f.__name__

        self.f = f
        self.defaults = {} # param's default value
        self.types = {}    # param's type annotation

        params = inspect.signature(self.f).parameters
        self.names = [*params]

        for x in params:
            v = params[x].default

            if v == inspect._empty:
                # no default value
                cls = params[x].annotation
                if cls != inspect._empty:
                    self.types[x] = cls
            else:
                # has default value
                self.defaults[x] = v
                self.types[x] = type(v)

    def __call__(self, req, *args, **kwargs):
        try:
            r = self.f(*args, **kwargs)

            if isinstance(r, HttpResponseBase):
                return r

            return JsonResponse({
                    'error': None,
                    'result': r, 
                }, safe = False)
        except:
            return JsonResponse({
                    'error': sys.exc_info()[0],
                    'result': None, 
                }, safe = False)


    @property
    def param_url(self):
        def get_type(x):
            try:
                return self.types[x].__name__ + ':'
            except KeyError:
                return ''

        return '/'.join([ '/'.join((x, '<' + get_type(x) + x + '>' )) for x in self.names ])


def api(f):
    """ api decorator 
    
    @api
    def add(a,b):
        return a+b

    the api's url => {pkg_mnt}/{module}/{func_name}/a/1/b/2

    """
    _urls.append(_APIWrapper(f))
    return f
