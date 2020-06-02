''' Internal utility functions used by high level module '''
import sys
import inspect
import enum

def get_class(func):
    ''' extract class object of member function

        returns None for top-level function
    '''
    parts = func.__qualname__.split('.')[:-1]

    cls = None

    if parts:
        if '<locals>' in parts:
            if hasattr(func, '__self__'):
                # bounded
                self = func.__self__
                if isinstance(self, type):
                    # class-method
                    return self
                return type(self)
            
            # we cannot resolve the class of unbounded local scope function
            raise ValueError(f'class of nested unbound function {func.__qualname__}'
                             'cannot be resolved'
                             )
        else:
            mod = sys.modules[func.__module__]
            for i, name in enumerate(parts):
                if i == 0:
                    cls = getattr(mod, name)
                else:
                    cls = getattr(cls, name)

    return cls

class FuncType(enum.IntEnum):
    PLAIN = 0,  # plain function
    STATIC_METHOD = 1, # @staticmethod of a class
    CLASS_METHOD = 2,  # @classmethod of a class
    METHOD = 3  # normal self-bounded function of a class 

def get_typeinfo(func)->(FuncType, type):
    ''' get function type info 
       returns (FuncType, Class)
    '''

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
    else:
        # either class-method or bounded method
        if isinstance(func.__self__, type):
            return (FuncType.CLASS_METHOD, cls)

        return (FuncType.METHOD, cls)





