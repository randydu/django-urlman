""" URL management """

import sys
import importlib
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


def _geturl(prj, app_paths, pkg, module, fname, param_url, *, module_maps=None, app_url=None):
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
        except:
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

        if fname:
            parts.append(fname)
    else:
        # app-wide url is specified
        parts = app_url.strip(' /').split('/')

    if anchor == '':
        url = '/'.join(parts)
    else:
        url = '/'.join([anchor.rstrip('/'), ] + parts)

    url += param_url

    # force trailing slash to avoid potential django route resolving issue.
    if not url.endswith('/'):
        url += '/'
    # no leading slash to make django system check happy.
    if url != '/':
        url = url.lstrip('/')

    return url


def _get_all_paths(prj: str, apps: dict):
    """ get all all registered urls """

    def resolve_final_handler(x):
        # the original handler might have been wrapped by extra decorators,
        # so we must figure out the final handler as the view
        if not hasattr(x.f, '__name__'):
            # class-based view, once wrapped by external (non-django-urlman) decorator,
            # cannot be resolved, just returns the api-wrapper itself.
            warnings.warn(
                f'class-based view {x.f.__class__.__name__} is not compatible'
                'with external decorators.')
            return x

        try:
            m = sys.modules[x.f.__module__]
            y = getattr(m, x.f.__name__)
            # if x is not y:
            #    print(f'external decorator detected, {x.__name__}')
            return y
        except:
            warnings.warn(
                f'view {x.f.__name__} cannot be resolved,  might be modified by'
                'imcompatible external decorators, or defined in local scope.')
            return x

    # resolve paths
    paths = []
    # for pkg, module, api, handler in _urls:
    for x in _urls:
        if x.site_url is None:
            # site_url not specified, resolve it...
            m = sys.modules[x.f.__module__]
            x.site_url = _geturl(
                prj, apps, m.__package__, x.f.__module__, x.func_name,
                x.param_url, app_url=x.url)

    # check duplicated site-url, merge the handlers if possible
    # (method-based dispatch) or raise error if duplication cannot be resolved.

    for x in _urls:
        xpath = django.urls.re_path if x.has_optional_param else django.urls.path
        paths.append(
            xpath(x.site_url, resolve_final_handler(x), name=x.url_name))

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
        for app in apps:
            if isinstance(app, str) and app != prj:  # don't load project
                m = importlib.import_module(app)
                if hasattr(m, '__path__'):
                    import pkgutil
                    # package, loading all modules except special files (setup.py)
                    for _, name, _ in pkgutil.iter_modules(m.__path__):
                        if name not in ('setup',
                                        'manage', 'migrations', 'settings', 'asgi', 'wsgi'):
                            importlib.import_module('.'+name, package=app)

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

    def default(self, obj):
        try:
            return super().default(obj)
        except:
            # To minimize serialized data size, only instantiated fields are saved and
            # the fields defined in class are ignored.
            result = dict(obj.__dict__) if self.enable_all_fields else {
                k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
            if self.include_cls_id:
                result['_cls_'] = type(obj).__name__
            return result


class _APIWrapper:
    """ Request handler for wrapped api """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, func, is_url=False, **kwargs):
        functools.update_wrapper(self, func, updated=())

        self.f = func
        self.func_name = kwargs.get('func_name', func.__name__ if hasattr(
            func, '__name__') else func.__class__.__name__)
        self.url_name = kwargs.get(
            'name', func.__module__ + '.' + self.func_name)
        self.url = kwargs.get('url', None)  # app-wide url
        self.site_url = kwargs.get('site_url', None)  # site-wide url
        self.methods = {*[x.upper() for x in kwargs.get('methods', [])]}

        self._is_url = is_url

        self.defaults = {}  # param's default value
        self.types = {}    # param's type annotation
        self.pos_call = []  # pass param by position
        self.pos_only = []  # position only param
        # param should be retrieved from body, query
        self.param_autos = kwargs.get('param_autos', ())

        params = inspect.signature(func).parameters

        param_types = kwargs.get('param_types', {})

        self.names = [*params]
        if is_url:
            # skip first parameter (request)
            self.names = self.names[1:]

        for i, name in enumerate(self.names):
            param = params[name]

            if (param.kind == inspect.Parameter.POSITIONAL_ONLY or
                    param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD):
                # call by position
                assert len(self.pos_call) == i
                self.pos_call.append(name)

                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    self.pos_only.append(name)

            value = param.default

            if value == inspect._empty:
                # no default value
                cls = param.annotation
                if cls != inspect._empty:
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

        if self.pos_call:
            # extract call_by_pos params
            myargs = []
            for param in self.pos_call:
                myargs.append(kwargs[param])
                kwargs.pop(param)

            if self._is_url:
                if kwargs:
                    result = self.f(req, *myargs, **kwargs)
                else:
                    result = self.f(req, *myargs)
            else:
                if kwargs:
                    result = self.f(*myargs, **kwargs)
                else:
                    result = self.f(*myargs)
        else:
            if self._is_url:
                result = self.f(req, **kwargs)
            else:
                result = self.f(**kwargs)

        return result

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

    def __call__(self, req, **kwargs):
        """ entry point of request handling called by diango.
            * args is never used by diango when calling, all parameters are passed via keyword-values.
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
                        found = False
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
                                mykwargs[name] = self.defaults[name]
                                found = True
                        else:
                            mykwargs[name] = self._type_cast(name, value)

                        if not found:  # param cannot be binded from inputs
                            return HttpResponseBadRequest('parameter (%s) not found' % name)

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

                return f"/<{typ}{param}>" if param in self.pos_only else f"/{param}/<{typ}{param}>"

        return ''.join([get_one_url(x) for x in self.names if x not in self.param_autos])

    @property
    def has_optional_param(self):
        """ if the handler has any optional parameter?

            For handler with optional parameter, we use re_path() instead of path()
            in the urlconf registry.
        """
        return self.defaults != {}


def _wrap(func, is_url, **kwargs):
    wrp = _APIWrapper(func, is_url, **kwargs)
    _urls.append(wrp)
    return wrp


def _api(func=None, is_url=False, **kwargs):
    if callable(func):
        # decorator without parameters, or called directly with api(f)
        return _wrap(func, is_url, **kwargs)

    # decorator with parameters
    def wrap(func):
        return _wrap(func, is_url, **kwargs)
    return wrap


api = functools.partial(_api, is_url=False)
url = functools.partial(_api, is_url=True)


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
        'wrapper cannot be resolved, is it wrapped with @api/@url before?')


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

# debug helpers


def _dump_urls():
    """ dump internal urls (internal) """

    print('*** Dump of all registered urls ***\n')

    for i, wrp in enumerate(_urls):
        print(f'[{i}] {wrp.site_url}\n')
