from django_urlman.urlman import _geturl, _APIWrapper, _get_wrapper, api, url, mount, map_module, APIResult

from . import settings


def test_geturl():
    prj = "coolsite"
    assert _geturl(prj, {}, '', 'health', 'ping', '') == 'health/ping/'
    assert _geturl(prj, { 'mymath': 'math'} , 'mymath', 'mymath.algo', 'add', '') == 'math/algo/add/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', '') == 'math/algo/add/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', '', '') == 'math/algo/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', '', '/xx') == 'math/algo/xx/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', '/a/<int:a>/b/<int:b>') == 'math/algo/add/a/<int:a>/b/<int:b>/'

    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', '', module_maps = {'mymath.algo':''}) == 'math/add/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced', 'add1', '', 
        module_maps = {'mymath.algo':''}) == 'math/advanced/add1/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced', 'add1', '', 
        module_maps = {'mymath.algo':'', 'mymath.algo.advanced':'super'}) == 'math/super/add1/'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo.advanced.internal', 'add2', '', 
        module_maps = {'mymath.algo':'base', 'mymath.algo.advanced':'super'}) == 'math/super/internal/add2/'

    assert _geturl(prj, {}, '', 'health', 'ping', '', app_url="check") == 'health/check/'

def test_api_param_url():
    @api
    def f(a,b): pass
    assert _get_wrapper(f).param_url == '/a/<a>/b/<b>'

    @api
    def typed(a:int,b:int): pass
    assert _get_wrapper(typed).param_url == '/a/<int:a>/b/<int:b>'

    @api
    def typed_mixed(a:int,b): pass
    assert _get_wrapper(typed_mixed).param_url == '/a/<int:a>/b/<b>'

    @api
    def optional(a:int,b=1): pass
    assert _get_wrapper(optional).param_url == '/a/(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'

    @api
    def pos_only(a,/,b):pass
    assert _get_wrapper(pos_only).param_url == '/<a>/b/<b>'

    @api
    def pos_only_and_optional1(a:int,/,b=1):pass
    assert _get_wrapper(pos_only_and_optional1).param_url == '/(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'

    @api
    def pos_only_and_optional2(a:int,b=1,/):pass
    assert _get_wrapper(pos_only_and_optional2).param_url == '/(?P<a>[0-9]+)(?:/(?P<b>[0-9]+))?'

    @api
    def pos_only_and_optional1(a:int=0,/):pass
    assert _get_wrapper(pos_only_and_optional1).param_url == '(?:/(?P<a>[0-9]+))?'


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


def test_class_based_view():
    class SayHello:
        def __call__(self, who):
            return 'hello ' + who
    
    h = SayHello()
    api(h)
    assert _get_wrapper(h).param_url == '/who/<who>'

#urlpatterns =[]

def test_site_url():
    @api
    def hey():pass
    
    # api_binding_auto
    @api(param_autos=('a'))
    def t1(a:int):
        return a

    @api(url='')
    def index():pass

    @api
    def hello(a=1):
        return a


    map_module(__name__,'')
    # mount(urlconf=__name__) # mount all registered apis
    mount(only_me=True) # mount all registered apis

    
    # --- hey ---
    wrp = _get_wrapper(hey)
    assert wrp.url == None
    assert wrp.site_url == 'hey/'

    assert _get_wrapper(index).site_url == '/'


    # test auto-binding
    url =_get_wrapper(t1).site_url
    assert url == 't1/'

    from django.test import Client
    client = Client()

    response = client.post('/t1/',{'a':2}, content_type='application/json')
    assert response.status_code == 200
    r = APIResult(response)
    assert r.error == None
    assert r.result == 2

    response = client.post('/t1/',{'a':3})
    assert response.status_code == 200
    r = APIResult(response)
    assert r.error == None
    assert r.result == 3

    response = client.post('/t1/?a=4')
    assert response.status_code == 200
    r = APIResult(response)
    assert r.error == None
    assert r.result == 4

    # api-binding
    url =_get_wrapper(hello).site_url
    assert url == 'hello(?:/a/(?P<a>[0-9]+))?/'

    response = client.get('/hello/')
    assert response.status_code == 200
    
    r = APIResult(response)
    assert r.error == None
    assert r.result == 1
    
    response = client.get('/hello/a/2/')
    r = APIResult(response)
    assert r.error == None
    assert r.result == 2