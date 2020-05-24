from django_urlman.urlman import _geturl, _APIWrapper

def test_geturl():
    prj = "coolsite"
    assert _geturl(prj, {}, '', 'health', 'ping', '') == 'health/ping'
    assert _geturl(prj, { 'mymath': 'math'} , 'mymath', 'mymath.algo', 'add', '') == 'math/algo/add'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', '') == 'math/algo/add'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', 'a/<int:a>/b/<int:b>') == 'math/algo/add/a/<int:a>/b/<int:b>'

    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', '', module_maps = {'mymath.algo':''}) == 'math/add'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced', 'add1', '', 
        module_maps = {'mymath.algo':''}) == 'math/advanced/add1'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced', 'add1', '', 
        module_maps = {'mymath.algo':'', 'mymath.algo.advanced':'super'}) == 'math/super/add1'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced.internal', 'add2', '', 
        module_maps = {'mymath.algo':'base', 'mymath.algo.advanced':'super'}) == 'math/super/internal/add2'


def test_api_param_url():
    def f(a,b): pass
    assert _APIWrapper(f).param_url == 'a/<a>/b/<b>'

    def typed(a:int,b:int): pass
    assert _APIWrapper(typed).param_url == 'a/<int:a>/b/<int:b>'

    def typed_mixed(a:int,b): pass
    assert _APIWrapper(typed_mixed).param_url == 'a/<int:a>/b/<b>'

    def optional(a:int,b=1): pass
    assert _APIWrapper(optional).param_url == 'a/(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'

    def pos_only(a,/,b):pass
    assert _APIWrapper(pos_only).param_url == '<a>/b/<b>'

    def pos_only_and_optional(a:int,/,b=1):pass
    assert _APIWrapper(pos_only_and_optional).param_url == '(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'

    def pos_only_and_optional1(a:int=0,/):pass
    assert _APIWrapper(pos_only_and_optional1).param_url == '(?:(?P<a>[0-9]+))?'