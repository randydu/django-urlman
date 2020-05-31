""" Wrapper Protocal 
"""

_MARK = '_mark_'

def mark(deco):
    ''' decorator to setup bi-directional linkage between wrapper
    and wrapped functions.
    '''
    def _update_mark(obj, val):
        orig = getattr(obj, _MARK, {})
        orig.update(val)
        setattr(obj, _MARK, orig)

    def wrap(func):
        result = deco(func)

        _update_mark(func, {
            'wrapper': result,
            'wrapper_decorator': deco,
        })

        _update_mark(result, {
            'wrapped': func,
        })

        return result

    return wrap
