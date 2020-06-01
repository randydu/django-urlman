""" Wrapper Protocal """

import functools

_MARK = '_mark_'


def mark(deco):
    ''' decorator modifier to setup bi-directional linkage between wrapper
    and wrapped functions.
    '''
    def _update_mark(obj, val):
        orig = getattr(obj, _MARK, {})
        orig.update(val)
        setattr(obj, _MARK, orig)

    def wrap(func):
        result = deco(func)

        _update_mark(func, {
            'wrapper': (result, deco)
        })

        _update_mark(result, {
            'wrapped': func,
        })

        return result

    return wrap


# utility functions
def _get_mark_info(obj, item):
    try:
        return getattr(obj, _MARK)[item]
    except KeyError:
        return None


mark_wrapper = functools.partial(_get_mark_info, item='wrapper')
mark_wrapper.__doc__ = (
    'get the wrapper of the object'
    '    returns None if obj is not marked or no wrapper'
)

mark_wrapped = functools.partial(_get_mark_info, item='wrapped')
mark_wrapped.__doc__ = (
    'get the wrapped function of the object'
    '    returns None if obj is not marked or no wrapped'
)


def is_marked(obj):
    ''' detect if obj is modified by marked decorator? '''
    return hasattr(obj, _MARK)
