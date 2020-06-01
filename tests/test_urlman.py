from django_urlman.urlman import _geturl, _APIWrapper, mount, module_path, APIResult, get_wrapper
from django_urlman.decorators import api, url, HEAD, GET, POST, PUT, PATCH, DELETE, READ, WRITE
from django_urlman.marker import mark

from django.views.decorators.http import require_http_methods, require_GET, require_POST, require_safe

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
    assert (f).param_url == '/a/<a>/b/<b>'

    @api
    def typed(a:int,b:int): pass
    assert (typed).param_url == '/a/<int:a>/b/<int:b>'

    @api
    def typed_mixed(a:int,b): pass
    assert (typed_mixed).param_url == '/a/<int:a>/b/<b>'

    @api
    def optional(a:int,b=1): pass
    assert (optional).param_url == '/a/(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'

    @api
    def pos_only(a,/,b):pass
    assert (pos_only).param_url == '/<a>/b/<b>'

    @api
    def pos_only_and_optional1(a:int,/,b=1):pass
    assert (pos_only_and_optional1).param_url == '/(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'

    @api
    def pos_only_and_optional2(a:int,b=1,/):pass
    assert (pos_only_and_optional2).param_url == '/(?P<a>[0-9]+)(?:/(?P<b>[0-9]+))?'

    @api
    def pos_only_and_optional3(a:int=0,/):pass
    assert (pos_only_and_optional3).param_url == '(?:/(?P<a>[0-9]+))?'


def test_names():
    # override api name by 'func_name'
    @api(func_name='details1')
    def show_details1(a:int,b:int): pass

    wrp =(show_details1)
    assert wrp.func_name == 'details1'
    assert wrp.url_name == show_details1.__module__ + '.details1'

    @api(func_name='details2', name='xxx')
    def show_details2(a:int,b:int): pass

    wrp =(show_details2)
    assert wrp.func_name == 'details2'
    assert wrp.url_name == 'xxx'


def test_class_based_view():
    class SayHello:
        def __call__(self, who):
            return 'hello ' + who
    
    h = api(SayHello())
    assert (h).param_url == '/who/<who>'

#urlpatterns =[]

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

@api(methods=['GET'])
def get_only1():
    pass

@GET
@api
def get_only2():
    pass

@READ
@api
def read_only():
    pass

@WRITE
@api
def write_only():
    pass

# django compatibility test
@mark(require_GET)
@api
def get_only():
    pass

# GET/POST dispatcb
_name = 'Ruby'
@GET
@api
def name():
    global _name
    return _name

@PUT
@api(param_autos=['name'])
def name(name,/): # pylint: disable=function-redefined
    global _name
    old_name, _name = _name, name
    return old_name


def test_site_url():
    module_path(__name__,'')
    # mount(urlconf=__name__) # mount all registered apis
    mount(only_me=True) # mount all registered apis

    
    # --- hey ---
    wrp = (hey)
    assert wrp.url == None
    assert wrp.site_url == 'hey/'

    assert (index).site_url == '/'


    # test auto-binding
    url =(t1).site_url
    assert url == 't1/'

    from django.test import Client
    client = Client()

    response = client.post('/t1/',{'a':2}, content_type='application/json') # body: application/json
    assert response.status_code == 200
    r = APIResult(response)
    assert r.error == None
    assert r.result == 2

    response = client.post('/t1/',{'a':3}) # from body: multipart/form-data
    assert response.status_code == 200
    r = APIResult(response)
    assert r.error == None
    assert r.result == 3

    response = client.post('/t1/?a=4') # from query-string
    assert response.status_code == 200
    r = APIResult(response)
    assert r.error == None
    assert r.result == 4

    client.cookies['a'] = 5
    response = client.post('/t1/') # from cookie
    assert response.status_code == 200
    r = APIResult(response)
    assert r.error == None
    assert r.result == 5

    if False: #todo: setup testing env properly
        client.cookies.pop('a')
        client.session['a'] = 6
        response = client.post('/t1/') # from session
        assert response.status_code == 200
        r = APIResult(response)
        assert r.error == None
        assert r.result == 6

    # api-binding
    url =(hello).site_url
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

    # method
    response = client.get('/get_only1/')
    r = APIResult(response)
    assert r.error == None
    
    response = client.get('/get_only2/')
    r = APIResult(response)
    assert r.error == None

    response = client.post('/get_only2/')
    assert response.status_code == 405 # not allowed

    # read
    response = client.head('/read_only/')
    assert response.status_code == 200 # allowed
    response = client.get('/read_only/')
    assert response.status_code == 200 # allowed

    response = client.post('/read_only/')
    assert response.status_code == 405 # not allowed
    response = client.put('/read_only/')
    assert response.status_code == 405 # not allowed
    response = client.patch('/read_only/')
    assert response.status_code == 405 # not allowed


    # write
    response = client.head('/write_only/')
    assert response.status_code == 405 # not allowed
    response = client.get('/write_only/')
    assert response.status_code == 405 # not allowed

    response = client.post('/write_only/')
    assert response.status_code == 200 # allowed
    response = client.put('/write_only/')
    assert response.status_code == 200 # allowed
    response = client.patch('/write_only/')
    assert response.status_code == 200 # allowed

    # django compatibility test
    response = client.head('/get_only/')
    assert response.status_code == 405 # not allowed
    response = client.get('/get_only/')
    assert response.status_code == 200 # allowed

    response = client.post('/get_only/')
    assert response.status_code == 405 # not allowed
    response = client.put('/get_only/')
    assert response.status_code == 405 # not allowed
    response = client.patch('/get_only/')
    assert response.status_code == 405 # not allowed

    assert get_wrapper(get_only).site_url == 'get_only/'

    # test method-based dispatch
    response = client.get('/name/')
    assert response.status_code == 200
    assert response.json()['result'] == 'Ruby'

    response = client.put('/name/?name=Janet')
    assert response.status_code == 200
    assert response.json()['result'] == 'Ruby' # last name

    response = client.get('/name/')
    assert response.status_code == 200
    assert response.json()['result'] == 'Janet'