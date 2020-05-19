# django-urlman
URL manager for Django
======================

Django is powerful, we want it to be as simple as possible to use without sacrificing flexibility.

Usage
------

In project's urls.py:

```python

from django_urlman import mount

urlpatterns = [
    # original django urls
    path('polls/', include('polls.urls')),
    path('admin/', admin.site.urls),

    # django-urlman aware apps
    * mount('app1/', 'app1'),
    * mount('app2/', 'app2'),
]

```

In app1 module:

```python
from django_urlman import url

@url
def hi(_):
    return HttpResponse('Hello World')

```

Then the api endpoint "app1/hi" should return "Hello World". 
