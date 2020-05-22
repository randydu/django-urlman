
# Extra converters 

import django.urls

class FloatConverter:
    regex = '[+-]?([0-9]*[.])?[0-9]+'

    def to_python(self, value):
        return float(value)

    def to_url(self, value):
        return str(value)


django.urls.register_converter(FloatConverter, 'float')
