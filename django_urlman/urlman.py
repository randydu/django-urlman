""" URL management """

import sys
import importlib
import pkgutil
import inspect
import traceback
import functools
import json
import warnings

import django.conf
import django.urls
from django.http.response import (HttpResponseBase, JsonResponse,
                                  HttpResponseNotAllowed, HttpResponseBadRequest)
from django.core.serializers.json import DjangoJSONEncoder
from django.urls.converters import get_converters

# make sure built-in converters are registered.
from . import converters  # pylint: disable=unused-import

from . import marker
from .utils import FuncType, get_typeinfo

_urls = []
_module_maps = {}  # module oaths
_app_maps = {}  # app paths


def module_path(module, path):
    """ maps module to a url """
    if inspect.ismodule(module):
        name = module.__name__
    elif isinstance(module, str):
        try:
            # valid module?
            _ = sys.modules[module]
            name = module
        except KeyError:
            raise ValueError(f"'{module}' is not a valid module'")
    else:
        raise ValueError("'module' must be either a module or a module name")

    _module_maps[name] = path


def app_path(pkg, path):
    """ maps app package to a url """
    if isinstance(pkg, str):
        pkg = sys.modules[pkg]

    name = pkg.__name__
    if not inspect.ismodule(pkg) or not hasattr(pkg, '__path__'):
        raise ValueError(f"'{name}' must be a package")

    _app_maps[name] = path

# pylint: disable=(too-many-arguments, too-many-locals)


def _geturl(prj, app_paths, pkg, module, clsname, fname, param_url, *,
            module_maps=None, app_url=None):
    """ deduce url from meta info """
    module_maps = module_maps or _module_maps
    segs = module.split('.')
    app = pkg if pkg != '' else segs[0]
    # project module always mounts at '/'
    anchor = app_paths.get(app, _app_maps.get(app, app)) if app != prj else ''

    if app_url is None:
        parts = segs[1:]
        try:
            # exact match first
            parts = module_maps[module].split('/')
        except KeyError:
            # searching partial matching
            for i in sorted(module_maps, key=len, reverse=True):
                if module.startswith(i):
                    leftover = module[len(i):]
                    if len(leftover) == 0:
                        parts = module_maps[i].split('/')
                        break
                    if leftover[0] == '.':
                        parts = module_maps[i].split(
                            '/') + leftover[1:].split('.')
                        break

        while parts and parts[0] == '':
            parts = parts[1:]

        if clsname:
            parts.append(clsname)

        if fname:
            parts.append(fname)
    else:
        # app-wide url is specified
        parts = app_url.strip(' /').split('/')

    # full-path composition
    fpath = '/'.join(parts) if anchor == '' else (
        '/'.join([anchor.rstrip('/'), ] + parts)
    )

    fpath += param_url

    # force trailing slash to avoid potential django route resolving issue.
    if not fpath.endswith('/'):
        fpath += '/'
    # no leading slash to make django system check happy.
    if fpath != '/':
        fpath = fpath.lstrip('/')

    return fpath


def _resolve_final_handler_old(wrp):
    # the original handler might have been wrapped by extra decorators,
    # so we must figure out the final handler as the view
    if not hasattr(wrp.func, '__name__'):
        # class-based view, once wrapped by external (non-django-urlman) decorator,
        # cannot be resolved, just returns the api-wrapper itself.
        warnings.warn(
            f'class-based view {wrp.func.__class__.__name__} is not compatible'
            'with external decorators.')
        return wrp

    # SHOULD revise the conflicts with method-based dispatch
    try:
        mod = sys.modules[wrp.func.__module__]
        handler = getattr(mod, wrp.func.__name__)
        # if wrp is not handler:
        #    print(f'external decorator detected, {wrp.__name__}')
        return handler
    except (KeyError, AttributeError):
        warnings.warn(
            f'view {wrp.func.__name__} cannot be resolved,  might be modified by'
            'imcompatible external decorators, or defined in local scope.')
        return wrp


def _resolve_final_handler(wrp):
    # resolve the final handler as the outmost marked wrapper
    return marker.get_outmost_wrapper(wrp)

# pylint: disable=too-few-public-methods


class _MultiHandlers:
    ''' multiple handlers sharing the same site-url '''

    def __init__(self, handlers):
        '''
        handlers is a list of the following pattern:

        handlers: [
            (['PUT',], handler1),
            (['GET',], handler2),
            ...
        ]
        '''
        super().__init__()

        self._handlers = handlers
        self.methods = {method for methods,
                        _ in handlers for method in methods}

    def __call__(self, req, **kwargs):
        method = req.method.upper()

        for methods, handler in self._handlers:
            if method in methods:
                return handler(req, **kwargs)

        return HttpResponseNotAllowed(self.methods)


def _check_multi_handlers(wrps):
    ''' check consistency of multiple wrappers sharing the same site-url.
     (method-based dispatch) or raise error if duplication cannot be resolved.
    '''
    assert len(wrps) > 1
    site_url = wrps[0].site_url
    url_name = wrps[0].url_name

    # (1) no catch-all handler (methods =[])
    if any(not wrp.methods for wrp in wrps):
        raise ValueError(f'multi-handlers of site ({site_url}) '
                         'has catch-all handler'
                         )

    # (2) no method conflicting
    methods = {method for wrp in wrps for method in wrp.methods}
    if len(methods) < sum(len(wrp.methods) for wrp in wrps):
        raise ValueError(f'multi-handlers of site ({site_url}) '
                         'have conflicting http-method'
                         )
    # (3) no url-name conflicting
    if any(url_name != wrp.url_name for wrp in wrps):
        raise ValueError(f'multi-handlers of site ({site_url}) '
                         'have conflicting url_name'
                         )


def _get_all_paths(prj: str, apps: dict):
    """ get all all registered urls """

    grouped_wrps = {}  # wrappers grouped by site-url
    for wrp in _urls:
        # make sure the api can be called properly
        wrp.cls = None if wrp.cls_resolver is None else wrp.cls_resolver()
        if wrp.func_type in (FuncType.METHOD, FuncType.CLASS_METHOD) \
                and wrp.cls is None:
            raise ValueError(
                f'class of member function "{wrp.func_name}" cannot be resolved.\n'
                'as a result the api cannot be called later!\n'
                'please do not put the class definiation inside a function.'
            )

        if wrp.site_url is None:
            # site_url not specified, resolve it...
            mod_name = wrp.real_func.__module__
            mod = sys.modules[mod_name]
            wrp.site_url = _geturl(
                prj, apps, mod.__package__, mod_name,
                '' if wrp.cls is None else wrp.cls.__name__,
                wrp.func_name, wrp.param_url, app_url=wrp.url
            )

        try:
            wrps = grouped_wrps[wrp.site_url]
            wrps.append(wrp)
        except KeyError:
            grouped_wrps[wrp.site_url] = [wrp]

    # resolve paths
    paths = []

    for site_url, wrps in grouped_wrps.items():
        wrp = wrps[0]
        url_name = wrp.url_name
        xpath = django.urls.re_path if wrp.has_optional_param else django.urls.path

        if len(wrps) == 1:  # unique handler
            paths.append(
                xpath(site_url, _resolve_final_handler(wrp), name=url_name)
            )
        else:
            _check_multi_handlers(wrps)

            paths.append(
                xpath(site_url, _MultiHandlers([
                    (wrp.methods, _resolve_final_handler(wrp)) for wrp in wrps
                ]), name=url_name)
            )

    return paths


def mount(apps: dict = None, *, urlconf=None, only_me=False):
    """ adds all registered api/url handlers """

    urlconf = urlconf or django.conf.settings.ROOT_URLCONF
    mroot = importlib.import_module(urlconf)
    prj = mroot.__package__
    # apps: if apps are not imported previously, it can be imported here.
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
        def load_package(app, path):
            # package, loading all modules except special files (setup.py)
            for _, name, _ in pkgutil.iter_modules(path):
                if name not in ('setup',
                                'manage', 'migrations', 'settings', 'asgi', 'wsgi'):
                    importlib.import_module('.'+name, package=app)

        for app in apps:
            if isinstance(app, str) and app != prj:  # don't load project itself
                mod = importlib.import_module(app)
                if hasattr(mod, '__path__'):
                    load_package(app, mod.__path__)

    apps = {} if apps is None else {
        (k if isinstance(k, str) else k.__name__): v for k, v in apps.items()
    }

    if only_me:
        mroot.urlpatterns = _get_all_paths(prj, apps)
    else:
        mroot.urlpatterns += _get_all_paths(prj, apps)


class _MyJSONEncoder(DjangoJSONEncoder):
    enable_all_fields = False  # include private fields?

    # include '_cls_' field indicating which class generates the data
    include_cls_id = False

    def default(self, o):
        try:
            return super().default(o)
        except TypeError:
            # To minimize serialized data size, only instantiated fields are saved and
            # the fields defined in class are ignored.
            result = dict(o.__dict__) if self.enable_all_fields else {
                k: v for k, v in o.__dict__.items() if not k.startswith('_')}
            if self.include_cls_id:
                result['_cls_'] = type(o).__name__
            return result

# pylint: disable=too-many-instance-attributes


class _APIWrapper:
    """ Request handler for wrapped api """

    def __init__(self, func, is_url=False, **kwargs):
        functools.update_wrapper(self, func, updated=())

        self.func = func

        is_classmethod = isinstance(func, classmethod)
        is_staticmethod = isinstance(func, staticmethod)
        # the original function @classmethod/@staticmethod is applied
        self.real_func = func.__func__ if is_classmethod or is_staticmethod else func

        try:
            self.func_name = kwargs['func_name']
        except KeyError:
            try:
                self.func_name = self.real_func.__name__
            except AttributeError:
                self.func_name = type(self.real_func).__name__

        try:
            self.url_name = kwargs['name']
        except KeyError:
            self.url_name = self.real_func.__module__ + '.' + self.func_name

        self.url = kwargs.get('url', None)  # app-wide url
        self.site_url = kwargs.get('site_url', None)  # site-wide url
        #self.methods = {*[x.upper() for x in kwargs.get('methods', [])]}
        self.methods = {x.upper() for x in kwargs.get('methods', [])}

        self._is_url = is_url

        self.defaults = {}  # param's default value
        self.types = {}    # param's type annotation
        self.pos_call = []  # pass param by position
        self.pos_only = []  # position only param
        # param should be retrieved from body, query
        self.param_autos = kwargs.get('param_autos', ())

        # class-based api?
        self.func_type, self.cls_resolver = get_typeinfo(self.real_func)
        if is_classmethod:
            self.func_type = FuncType.CLASS_METHOD
        elif is_staticmethod:
            self.func_type = FuncType.STATIC_METHOD

        self._parse_signature(kwargs.get('param_types', {}))

    def _parse_signature(self, param_types):
        ''' parse api signaure '''

        params = inspect.signature(self.real_func).parameters
        self.names = [*params]

        # skip "self"/"cls" first parameter
        if self.func_type in (FuncType.CLASS_METHOD, FuncType.METHOD):
            self.names = self.names[1:]

        if self._is_url:
            # skip fixed positional parameter (request)
            self.names = self.names[1:]

        for name in self.names:
            param = params[name]

            if (param.kind == inspect.Parameter.POSITIONAL_ONLY or
                    param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD):
                # call by position
                self.pos_call.append(name)

                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    self.pos_only.append(name)

            value = param.default

            if value == inspect.Signature.empty:
                # no default value
                cls = param.annotation
                if cls != inspect.Signature.empty:
                    self.types[name] = cls
                else:
                    # decorator provided type annotation via 'param_types'
                    if name in param_types:
                        self.types[name] = param_types[name]
            else:
                # has default value
                self.defaults[name] = value
                self.types[name] = type(value)

    def _invoke(self, req, **kwargs):
        """ invoke wrapped function """

        # extract call_by_pos params
        myargs = []

        if self.func_type == FuncType.CLASS_METHOD:
            myargs.append(self.cls)  # cls,  pylint: disable=no-member
        elif self.func_type == FuncType.METHOD:
            myargs.append(self.cls())  # self, pylint: disable=no-member

        if self._is_url:
            myargs.append(req)

        for param in self.pos_call:
            myargs.append(kwargs[param])
            kwargs.pop(param)

        return self.real_func(*myargs, **kwargs)

    def _type_cast(self, name, value):
        ''' cast param value to registered type '''
        if name in self.types:
            typ = self.types[name]

            if not isinstance(value, typ):
                try:
                    value = get_converters()[typ.__name__].to_python(value)
                except KeyError:
                    # no matched converter, fall back to type constructor
                    try:
                        value = typ(value)
                    except (ValueError, TypeError) as ex:
                        warnings.warn((
                            f"exception {ex} caught when type casting parameter "
                            f"{name} from '{value}' to type {typ.__name__}, "
                            f"type cast is skipped."
                        ))
        return value

    def _try_resolve_param(self, req, name):
        ''' try resolving parameter values from various sources
            return: (found, value), value make sense only if found == True
        '''
        found = False
        value = None

        if name in self.param_autos:
            if req.content_type == 'application/json':
                content = json.loads(req.body)
                if name in content:
                    value = content[name]
                    found = True
            else:
                # search in POST which is parsed from body.
                try:
                    value = req.POST[name]
                    found = True
                except KeyError:
                    pass

                # search in GET which is parsed from query-string.
                try:
                    value = req.GET[name]
                    found = True
                except KeyError:
                    pass

                # search in cookie
                try:
                    # value = req.get_signed_cookie(x)
                    value = req.COOKIES[name]
                    found = True
                except KeyError:
                    pass

                # search session
                if hasattr(req, 'session'):
                    try:
                        value = req.session[name]
                        found = True
                    except KeyError:
                        pass

        if not found:
            if name in self.defaults:
                value = self.defaults[name]
                found = True
        else:
            value = self._type_cast(name, value)

        return (found, value)

    def call(self, *args, **kwargs):
        """ call wrapped function as usual """
        if self.func_type in (FuncType.PLAIN, FuncType.STATIC_METHOD, FuncType.CLASS_CALLABLE):
            return self.real_func(*args, **kwargs)
        if self.func_type == FuncType.CLASS_METHOD:
            return self.real_func(self.cls, *args, **kwargs)
        if self.func_type == FuncType.METHOD:
            return self.real_func(self.cls(), *args, **kwargs)

    def __call__(self, req, **kwargs):
        """ entry point of request handling called by diango.
            * args is never used by diango when calling, all parameters are
            passed via keyword-values.
        """
        try:
            # check the method permission
            if self.methods and req.method.upper() not in self.methods:
                return HttpResponseNotAllowed(self.methods)

            if self.has_optional_param or self.param_autos:
                # re_path() does not cope with type conversion so we have to do it manually
                # non-empty param_autos means some params needed to be retrieved
                # from other parts of request
                mykwargs = {**kwargs}

                for name in self.names:
                    if name in mykwargs:
                        # param provided by caller
                        mykwargs[name] = self._type_cast(name, mykwargs[name])
                    else:
                        # param not provided by caller
                        found, value = self._try_resolve_param(req, name)
                        if found:
                            mykwargs[name] = value
                        else:
                            # param cannot be binded from inputs
                            return HttpResponseBadRequest(f'parameter ({name}) cannot be resolved')

                result = self._invoke(req, **mykwargs)

            else:
                # path() has done type conversion so just pass them directly to wrapped function
                result = self._invoke(req, **kwargs)

            if isinstance(result, HttpResponseBase):
                return result

            return JsonResponse({
                'error': None,
                'result': result,
            }, safe=False, encoder=_MyJSONEncoder)
        except Exception as ex:  # pylint: disable=broad-except
            ex_info = sys.exc_info()
            return JsonResponse({
                'error': repr(ex),
                'stack': traceback.format_exception(*ex_info),

                'result': None,
            }, safe=False, encoder=_MyJSONEncoder)

    @property
    def param_url(self):
        """ param-based url.

            '' if no param; it has the leading slash if needed, no trailing slash.
        """
        if self.defaults:
            # has optional parameter, use re_path()
            def get_one_url(param):
                regex = '[^/]+'

                if param in self.types:
                    typ = self.types[param].__name__
                    try:
                        regex = get_converters()[typ].regex
                    except KeyError:
                        # unregistered converter
                        pass

                if param in self.defaults:
                    # param is optional
                    if param in self.pos_only:
                        return f"(?:/(?P<{param}>{regex}))?"
                    return f"(?:/{param}/(?P<{param}>{regex}))?"

                # param is not optional
                if param in self.pos_only:
                    return f"/(?P<{param}>{regex})"
                return f"/{param}/(?P<{param}>{regex})"

        else:
            # no optional parameter, use path()
            def get_one_url(param):
                try:
                    typ = self.types[param].__name__ + ':'
                except KeyError:
                    typ = ''

                return f"/<{typ}{param}>" if param in self.pos_only \
                    else f"/{param}/<{typ}{param}>"

        return ''.join([get_one_url(x) for x in self.names if x not in self.param_autos])

    @property
    def has_optional_param(self):
        """ if the handler has any optional parameter?

            For handler with optional parameter, we use re_path() instead of path()
            in the urlconf registry.
        """
        return self.defaults != {}


def get_wrapper(func):
    ''' [INTERNAL] get the APIWrapper instance from wrapped function '''
    if isinstance(func, _APIWrapper):
        return func

    name = func.__name__ if hasattr(
        func, '__name__') else func.__class__.__name__
    module = func.__module__

    for wrp in _urls:
        if wrp.__module__ == module and wrp.__name__ == name:
            return wrp

    raise ValueError(
        'wrapper cannot be resolved, is it wrapped with @api/@url?')


class APIResult:
    '''utility to retrieve result of api from response'''

    def __init__(self, response):
        self.status_code = response.status_code
        self._r = json.loads(response.content)

    @property
    def error(self):
        ''' error information '''
        return self._r['error']

    @property
    def stack(self):
        ''' exception stack if error != null '''
        return self._r.get('stack', None)

    @property
    def result(self):
        ''' api result on success, can be basic type (str, int, float,...) or dict, list.
            result == null on error
        '''
        return self._r['result']

# debug helpers


def _dump_urls():
    """ dump internal urls (internal) """

    print('*** Dump of all registered urls ***\n')

    for i, wrp in enumerate(_urls):
        print(f'[{i}] {wrp.site_url}\n')
