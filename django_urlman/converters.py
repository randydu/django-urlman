
# Extra converters 

import django.urls

class FloatConverter:
    regex = '[+-]?([0-9]*[.])?[0-9]+'

    def to_python(self, value):
        return float(value)

    def to_url(self, value):
        return str(value)

class BoolConverter:
    regex = '(?i)true'

    def to_python(self, value):
        return bool(value)

    def to_url(self, value):
        return 'true' if value else 'false'

django.urls.register_converter(FloatConverter, 'float')
django.urls.register_converter(BoolConverter, 'bool')
