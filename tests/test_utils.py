''' test utility.py '''

from django_urlman.utils import get_class, get_typeinfo, FuncType

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

    assert get_class(C.f)() is C
    assert get_class(C.D.g)() is C.D

def test_top_levels_bounded():

    c = C()
    d = C.D()
    assert get_class(c.f)() is C
    assert get_class(d.g)() is C.D

def test_nested():
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

    assert get_class(E.e)() is E
    assert get_class(E.F.g)() is E.F

    assert get_class(eo.e)() is E
    assert get_class(eo.f)() is E
    assert get_class(fo.g)() is E.F
    assert get_class(fo.h)() is E.F

    # nested non-bounded function is not supported!
    with pytest.raises(ValueError):
        get_class(E.f)

    with pytest.raises(ValueError):
        get_class(E.F.h)

# -------- TypeInfo ----------
class A:
    def m(self):pass
    
    @staticmethod
    def s():pass

    @classmethod
    def c(cls):pass

def check(func, ft, cls):
    functype, fcls = get_typeinfo(func)
    cls0 = None if fcls is None else fcls()
    assert functype == ft
    assert cls0 == cls
def test_info():
    ''' test get_typeinfo '''

    check(A.m, FuncType.METHOD, A)
    check(A.s,FuncType.STATIC_METHOD, A)
    check(A.c, FuncType.CLASS_METHOD, A)

    a = A()
    check(a.m, FuncType.METHOD, A)
    check(a.s, FuncType.STATIC_METHOD, A)
    check(a.c, FuncType.CLASS_METHOD, A)

    class B:
        def m(self):pass
        
        @staticmethod
        def s():pass

        @classmethod
        def c(cls):pass

    check(B.m, FuncType.METHOD, None)
    check(B.s, FuncType.STATIC_METHOD, None)
    check(B.c, FuncType.CLASS_METHOD, B)

    b = B()
    check(b.m, FuncType.METHOD, B)
    check(b.s, FuncType.STATIC_METHOD, None)
    check(b.c, FuncType.CLASS_METHOD, B)

# Callable
class K:
    def __call__(self):
        pass

def test_callable():
    k = K()
    assert get_class(k)() == K
    check(k, FuncType.CLASS_CALLABLE, K)
