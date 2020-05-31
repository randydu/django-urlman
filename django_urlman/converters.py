""" Extra converters """

import django.urls


class FloatConverter:
    """ float type converter """
    regex = '[+-]?([0-9]*[.])?[0-9]+'

    @staticmethod
    def to_python(value):
        """ string to float """
        return float(value)

    @staticmethod
    def to_url(value):
        """ float to url string """
        return str(value)


class BoolConverter:
    """ bool type converter """
    regex = '(?i)(true|false)'

    @staticmethod
    def to_python(value):
        """ string to boolean """
        lstr = value.lower()
        if lstr in ('true', '1'):
            return True
        if lstr in ('false', '0'):
            return False

        raise ValueError(f'value ({value}) cannot be converted to bool')

    @staticmethod
    def to_url(value):
        """ boolean to string """
        return 'true' if value else 'false'


django.urls.register_converter(FloatConverter, 'float')
django.urls.register_converter(BoolConverter, 'bool')
