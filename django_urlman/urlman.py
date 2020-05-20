from django.urls import path

import importlib

_urls = []

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
    for pkg, module, api, handler in _urls:
        deps = module.split('.')
        app = pkg if pkg != '' else deps[0]
        anchor = apps.get(app, app) if app != prj else ''

        if anchor == '':
            url = '/'.join(deps[1:] + [api,])
        else:
            url = '/'.join([anchor,] + deps[1:] + [api,])

        print('\nurl: %s' % url )
        paths.append(path(url, handler))

    return paths



def url(f):
    """ url decorator for function """
    m = importlib.import_module(f.__module__)
    _urls.append((m.__package__, f.__module__, f.__name__, f))

    return f