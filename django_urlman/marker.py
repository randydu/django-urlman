""" decorator marker protocal """

import functools

_MARK = '_mark_'


def _update_mark(obj, val):
    orig = dict(getattr(obj, _MARK, {}))
    orig.update(val)
    setattr(obj, _MARK, orig)


def binding(wrapper, wrapped, decorator=None):
    ''' setup binding relathionship between wrapper and wrapped object '''
    _update_mark(wrapped, {
        'wrapper': (wrapper, decorator)
    })

    _update_mark(wrapper, {
        'wrapper': None,
        'wrapped': wrapped,
    })


def mark(deco):
    ''' decorator modifier to setup bi-directional linkage between wrapper
    and wrapped functions.
    '''

    def wrap(func):
        result = deco(func)
        binding(result, func, deco)
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
    'get the (wrapper, decorator) of the object'
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


def get_outmost_wrapper(obj):
    ''' returns the outmost wrapper '''
    cur = obj
    while True:
        nxt = mark_wrapper(cur)
        if nxt is None:
            return cur
        cur = nxt[0]  # wrapper only

def get_vanilla_wrapped(obj):
    ''' returns the original wrapped object '''
    cur = obj
    while True:
        nxt = mark_wrapped(cur)
        if nxt is None:
            return cur
        cur = nxt
