from django_urlman.converters import *
import re

def test_float():
    flt = FloatConverter()

    for s in ('0.0', '-1','+1','3.1415','+1','.3','-.3'):
        assert re.match(flt.regex, s).string == s

    
def test_bool():
    flt = BoolConverter()

    for s in ('true', 'TRUE','True','False','false','FALSE',):
        assert re.match(flt.regex, s).group(0) == s

    assert flt.to_python('True')
    assert flt.to_python('1')
    assert not flt.to_python('False')
    assert not flt.to_python('0')
