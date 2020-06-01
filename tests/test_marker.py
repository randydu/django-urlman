''' Test wrapper '''

from django_urlman.decorators import api
from django_urlman.marker import *

from django.views.decorators.http import (require_http_methods, require_GET,
                                          require_POST, require_safe)

def test_mark1():
    ''' test mark decorator '''

    def deco_a(func):
        def wrap(*args, **kwargs):
            return func(*args, **kwargs)
        return wrap

    def hello():
        pass

    wp1 = deco_a(hello)
    wp2 = mark(deco_a)(hello)

    assert type(wp1) is type(wp2)
    assert mark_wrapper(hello) == (
        wp2, deco_a)  # pylint: disable=(no-member, protected-access)
    assert mark_wrapped(
        wp2) is hello  # pylint: disable=(no-member, protected-access)


def test_mark2():
    ''' test mark decorator: chained '''

    def deco_a(func):
        def wrap(*args, **kwargs):
            return func(*args, **kwargs)
        return wrap

    def deco_b(func):
        def wrap(*args, **kwargs):
            return func(*args, **kwargs)
        return wrap

    @mark(deco_b)
    @mark(deco_a)
    def hello():  # pylint: disable=function-redefined
        pass

    # hello is now the outmost wrapper
    assert is_marked(hello)
    assert mark_wrapper(hello) is None

    # output of @mark(deco_a)
    wrp_a = mark_wrapped(hello)

    assert is_marked(wrp_a)
    assert mark_wrapper(wrp_a) == (hello, deco_b)

    # vanilla function
    orig = mark_wrapped(wrp_a)
    assert mark_wrapper(orig) == (wrp_a, deco_a)
    assert mark_wrapped(orig) is None

    assert get_outmost_wrapper(hello) is hello


def test_mark3():
    ''' test django built-in decorators '''
    @mark(require_GET)
    def f1(req):
        pass

    g = get_outmost_wrapper(f1)
    h = get_vanilla_wrapped(f1)

    @api
    def f2(req):
        pass

    g = get_outmost_wrapper(f2)
    h = get_vanilla_wrapped(f2)

    @mark(require_GET)
    @api
    def f3(req):
        pass

    g = get_outmost_wrapper(f3)
    h = get_vanilla_wrapped(f3)