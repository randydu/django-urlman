''' test utility.py '''

from django_urlman.utils import get_class

import pytest

def foo():
    pass

class C:
    def f(self): 
        pass

    class D:
        def g(self): 
            pass


def test_top_levels():
    assert get_class(foo) is None

    assert get_class(C.f) is C
    assert get_class(C.D.g) is C.D

def test_top_levels_bounded():

    c = C()
    d = C.D()
    assert get_class(c.f) is C
    assert get_class(d.g) is C.D

def test_wrapper():
    class E:
        @classmethod
        def e(cls):
            pass

        def f(self):
            pass

        class F:
            @classmethod
            def g(cls):
                pass
        
            def h(self): 
                pass

    eo = E()
    fo = E.F()

    assert get_class(E.e) is E
    assert get_class(E.F.g) is E.F

    assert get_class(eo.e) is E
    assert get_class(eo.f) is E
    assert get_class(fo.g) is E.F
    assert get_class(fo.h) is E.F

    # nested non-bounded function is not supported!
    with pytest.raises(ValueError):
        get_class(E.f)

    with pytest.raises(ValueError):
        get_class(E.F.h)