from django_urlman.urlman import _geturl, _APIWrapper, _get_wrapper, api, url

def test_geturl():
    prj = "coolsite"
    assert _geturl(prj, {}, '', 'health', 'ping', '') == 'health/ping/'
    assert _geturl(prj, { 'mymath': 'math'} , 'mymath', 'mymath.algo', 'add', '') == 'math/algo/add/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', '') == 'math/algo/add/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', '', '') == 'math/algo/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', '', 'xx') == 'math/algo/xx/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', 'a/<int:a>/b/<int:b>') == 'math/algo/add/a/<int:a>/b/<int:b>/'

    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', '', module_maps = {'mymath.algo':''}) == 'math/add/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced', 'add1', '', 
        module_maps = {'mymath.algo':''}) == 'math/advanced/add1/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced', 'add1', '', 
        module_maps = {'mymath.algo':'', 'mymath.algo.advanced':'super'}) == 'math/super/add1/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced.internal', 'add2', '', 
        module_maps = {'mymath.algo':'base', 'mymath.algo.advanced':'super'}) == 'math/super/internal/add2/'


def test_api_param_url():
    @api
    def f(a,b): pass
    assert _get_wrapper(f).param_url == 'a/<a>/b/<b>'

    @api
    def typed(a:int,b:int): pass
    assert _get_wrapper(typed).param_url == 'a/<int:a>/b/<int:b>'

    @api
    def typed_mixed(a:int,b): pass
    assert _get_wrapper(typed_mixed).param_url == 'a/<int:a>/b/<b>'

    @api
    def optional(a:int,b=1): pass
    assert _get_wrapper(optional).param_url == 'a/(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'

    @api
    def pos_only(a,/,b):pass
    assert _get_wrapper(pos_only).param_url == '<a>/b/<b>'

    @api
    def pos_only_and_optional(a:int,/,b=1):pass
    assert _get_wrapper(pos_only_and_optional).param_url == '(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'

    @api
    def pos_only_and_optional1(a:int=0,/):pass
    assert _get_wrapper(pos_only_and_optional1).param_url == '(?:(?P<a>[0-9]+))?'


def test_names():
    # override api name by 'func_name'
    @api(func_name='details')
    def show_details1(a:int,b:int): pass

    wrp =_get_wrapper(show_details1)
    assert wrp.func_name == 'details'
    assert wrp.url_name == show_details1.__module__ + '.details'

    @api(func_name='details', name='xxx')
    def show_details2(a:int,b:int): pass

    wrp =_get_wrapper(show_details2)
    assert wrp.func_name == 'details'
    assert wrp.url_name == 'xxx'