URL manager for Django
======================

Features
--------

* decorator based view registration, centralized url-conf is not needed;
* flexible function signature based, type-safe URL design;
* powerful api-binding: function parameter can be retrieved in URI, body, query-string, cookie or session;
* http methods control;
* compatible with django's view decorators;


Usage
------

Assume the django project is named 'mysite', in the project's root url-config file (mysite/urls.py):

```python
# mysite/urls.py:

from django_urlman import mount

urlpatterns = [
    # normal django urls
    path('admin/', admin.site.urls),
    ...
]

# mounting django-urlman powered apps
mount({
    'app1': 'app1/', # mount app1 at anchor 'app1/'
    'app2': 'app2/', # mount app2 at anchor 'app2/'
    ...
    })
```

In app1 module:

```python
# app1/test.py:

from django_urlman import api

@api
def hello():
    return 'Hello World!'

```

Then the api endpoint "app1/test/hello/" will return "Hello World!". 


URL Design
----------

Django uses path() and re_path() to specify the url of each view function in app's urls.py, it is the developer's responsiblity to make sure the URLs must match the function's signature in view file(s). If there are optional parameters then the URL regex-pattern of re_path() will be rather complex, if we use path() to enumerate all possible URL combinations, then there will be 2^N URLs mapped to the same view function with N optional parameters.

In django-urlman, URL design is quite simple --- the URL is automatically generated from the view function itself, and registered for you without editing in a centralized url-conf module.

Basically the URL of a function consists of several parts:

```
SITE_URL := <app_path> / APP_URL
APP_URL := <module_path> / <function_path> / <param_path>
```


