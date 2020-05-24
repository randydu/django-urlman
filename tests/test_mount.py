from django_urlman.urlman import _geturl, _APIWrapper

def test_geturl():
    prj = "coolsite"
    assert _geturl(prj, {}, '', 'health', 'ping', '') == 'health/ping'
    assert _geturl(prj, { 'mymath': 'math'} , 'mymath', 'mymath.algo', 'add', '') == 'math/algo/add'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', '') == 'math/algo/add'
    assert _geturl(prj, { 'mymath': 'math/'} , 'mymath', 'mymath.algo', 'add', 'a/<int:a>/b/<int:b>') == 'math/algo/add/a/<int:a>/b/<int:b>'

def test_api_param_url():
    def f(a,b): pass
    assert _APIWrapper(f).param_url == 'a/<a>/b/<b>'

    def g(a:int,b:int): pass
    assert _APIWrapper(g).param_url == 'a/<int:a>/b/<int:b>'

    def h(a:int,b): pass
    assert _APIWrapper(h).param_url == 'a/<int:a>/b/<b>'

    def w(a:int,b=1): pass
    assert _APIWrapper(w).param_url == 'a/(?P<a>[0-9]+)(?:/b/(?P<b>[0-9]+))?'