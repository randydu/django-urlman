''' Internal utility functions used by high level module '''
import sys
import inspect
import enum
import functools


def _must_be_callable(obj):
    ''' obj must be a callable '''
    if not callable(obj):
        raise ValueError('not a callable')


def _is_class_object(obj):
    ''' obj is a class based object? '''
    return type(obj).__name__ not in ('function', 'method')


def _try_resolve_class(module, parts):
    ''' try resolving class object from its name '''
    mod = sys.modules[module]
    cls = None
    for i, name in enumerate(parts):
        if i == 0:
            cls = getattr(mod, name)
        else:
            cls = getattr(cls, name)

    return cls

def get_class(func):
    ''' extract class object of a callable (function or class-object)

        returns None for top-level function, or function to resolve the
        class object

        Example:

        def hello():
            pass

        class Sample:
            def foo(self):
                pass

        assert get_class(hello) is None
        assert get_class(Sample.foo)() == Sample

    '''
    _must_be_callable(func)

    if _is_class_object(func):
        return lambda: type(func)

    # functions
    parts = func.__qualname__.split('.')[:-1]

    if not parts:
        return None

    if '<locals>' in parts:
        if hasattr(func, '__self__'):
            # bounded
            self = func.__self__
            if isinstance(self, type):
                # class-method
                return lambda: self
            return lambda: type(self)

        # we cannot resolve the class of unbounded local scope function
        raise ValueError(f'class of nested unbound function {func.__qualname__}'
                         'cannot be resolved'
                         )

    return functools.partial(_try_resolve_class,
                             module=func.__module__, parts=parts)


class FuncType(enum.IntEnum):
    ''' Function Type '''
    PLAIN = 0  # plain function
    STATIC_METHOD = 1  # @staticmethod of a class
    CLASS_METHOD = 2  # @classmethod of a class
    METHOD = 3  # normal self-bounded function of a class

    CLASS_CALLABLE = 4  # A class-based callable object


def get_typeinfo(func):
    ''' get function type info
       returns (FuncType, None or function to resolve class object)
    '''

    _must_be_callable(func)

    if _is_class_object(func):
        # class based callable object
        return FuncType.CLASS_CALLABLE, lambda: type(func)

    try:
        cls = get_class(func)
        if cls is None:
            return (FuncType.PLAIN, None)
    except ValueError:
        # class of nested unbound function cannot be resolved
        cls = None

    bounded = inspect.ismethod(func)
    if not bounded:
        # either static-method or unbounded method
        names = [*inspect.signature(func).parameters]
        if len(names) == 0 or names[0] != 'self':
            return (FuncType.STATIC_METHOD, cls)

        return (FuncType.METHOD, cls)

    # either class-method or bounded method
    if isinstance(func.__self__, type):
        return (FuncType.CLASS_METHOD, cls)

    return (FuncType.METHOD, cls)
