
# Extra converters 

import django.urls

class FloatConverter:
    regex = '[+-]?([0-9]*[.])?[0-9]+'

    def to_python(self, value):
        return float(value)

    def to_url(self, value):
        return str(value)

class BoolConverter:
    regex = '(?i)(true|false)'

    def to_python(self, value):
        s = value.lower()
        if s in ('true', '1'):
            return True
        elif s in ('false', '0'):
            return False
        
        raise ValueError(f'value ({value}) cannot be converted to bool')

    def to_url(self, value):
        return 'true' if value else 'false'

django.urls.register_converter(FloatConverter, 'float')
django.urls.register_converter(BoolConverter, 'bool')
