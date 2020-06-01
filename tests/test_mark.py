''' Test wrapper '''

from django_urlman.mark import *

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
    assert mark_wrapper(hello) == (wp2, deco_a) # pylint: disable=(no-member, protected-access)
    assert mark_wrapped(wp2) is hello # pylint: disable=(no-member, protected-access)

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
    def hello():
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