from django.urls import path


_urls = {}

def _getkey(x):
    return ":".join((x.__module__, x.__name__))

def mount(anchor:str, app:str):
    """ Mount app to project """
    import importlib

    m = importlib.import_module(app)

    if hasattr(m, '__path__'):
        import pkgutil
        # package
        for _, name, _ in pkgutil.iter_modules(m.__path__):
            if name not in ('setup'):
                importlib.import_module('.'+name, package=app)

    return ( path(anchor + api, handler) for key, (api, handler) in _urls.items() if key.startswith(app+':') )


def url(f):
    """ url decorator for function """
    _urls[_getkey(f)] = f.__name__, f

    return f