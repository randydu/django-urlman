''' Test wrapper '''

from django_urlman.wrapper import mark

def test_mark():
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
    assert hello._mark_['wrapper'] is wp2 # pylint: disable=(no-member, protected-access)
    assert hello._mark_['wrapper_decorator'] is deco_a # pylint: disable=(no-member, protected-access)
    assert wp2._mark_['wrapped'] is hello # pylint: disable=(no-member, protected-access)
