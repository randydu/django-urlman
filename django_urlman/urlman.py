import sys
import importlib
import inspect
import traceback

from django.urls import path, re_path
from django.http.response import HttpResponseBase, JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.urls.converters import get_converters

# make sure extra converters are registered.
from . import converters

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
        is_wrapper = isinstance(x, _APIWrapper)
        m = sys.modules[x.__module__]
        url = _geturl(prj, apps, m.__package__, x.__module__, x.__name__, x.param_url if is_wrapper else '')
        
        print('\nurl: %s' % url )

        xpath = re_path if is_wrapper and x.has_optional_param else path
        paths.append(xpath(url, x))

    return paths



def url(f):
    """ url decorator for function """
    _urls.append(f)
    return f

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
    def __init__(self, f):
        self.__module__ = f.__module__
        self.__name__ = f.__name__

        self.f = f
        self.defaults = {} # param's default value
        self.types = {}    # param's type annotation
        self.pos_call = []  # pass param by position
        self.pos_only = []  # position only param

        params = inspect.signature(self.f).parameters
        self.names = [*params]

        for i, x in enumerate(params):
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
                # has default value
                self.defaults[x] = v
                self.types[x] = type(v)

    def _invoke(self, *args, **kwargs):
        if self.pos_call:
            # extract call_by_pos params 
            myargs = []
            for x in self.pos_call:
                myargs.append(kwargs[x])
                kwargs.pop(x)
            myargs += args

            if kwargs:
                r = self.f(*myargs, **kwargs)
            else:
                r = self.f(*myargs)
        else:
            r = self.f(*args, **kwargs)
        
        return r


    def __call__(self, req, *args, **kwargs):
        try:
            if self.has_optional_param:
                # re_path() does not cope with type conversion so we have to do it manually
                mykwargs = { **kwargs }

                for x in self.names:
                    if x in mykwargs:
                        if x in self.types:
                            typ = self.types[x]
                            try:
                                v = get_converters()[typ.__name__].to_python(mykwargs[x])
                            except KeyError:
                                v = typ(mykwargs[x])
                            mykwargs[x] = v
                    else:
                        # param not provided by caller
                        if x in self.defaults:
                            mykwargs[x] = self.defaults[x]

                r = self._invoke(*args, **mykwargs)

            else:
                # path() has done type conversion so just pass them directly to wrapped function
                r = self._invoke(*args, **kwargs)

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
        if self.defaults:
            # has optional parameter, use re_path()
            def get_one_url(i,x):
                regex = '[^/]+'
                
                if x in self.types:
                    typ = self.types[x].__name__ 
                    try:
                        regex = get_converters()[typ].regex
                    except KeyError:
                        # unregistered converter 
                        pass

                delimeter = '' if i == 0 else '/'

                if x in self.defaults:
                    # x is optional
                    return f"(?:{delimeter}(?P<{x}>{regex}))?" if x in self.pos_only else f"(?:{delimeter}{x}/(?P<{x}>{regex}))?"
                else:
                    # x is not optional
                    return f"{delimeter}(?P<{x}>{regex})" if x in self.pos_only else f"{delimeter}{x}/(?P<{x}>{regex})"

        else:
            # no optional parameter, use path()
            def get_one_url(i,x):
                try:
                    typ = self.types[x].__name__ + ':'
                except KeyError:
                    typ = ''

                delimeter = '' if i == 0 else '/'
                return f"{delimeter}<{typ}{x}>" if x in self.pos_only else f"{delimeter}{x}/<{typ}{x}>"

        return ''.join([ get_one_url(i,x) for i,x in enumerate(self.names) ])

    @property
    def has_optional_param(self):
        return self.defaults != {}



def api(f):
    """ api decorator 
    
    @api
    def add(a,b):
        return a+b

    the api's url => {pkg_mnt}/{module}/{func_name}/a/1/b/2

    """
    _urls.append(_APIWrapper(f))
    return f
