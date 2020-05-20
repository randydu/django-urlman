from django_urlman import mount

def test_mount():
    paths = mount('', {
        'mymath': 'math/',
    })