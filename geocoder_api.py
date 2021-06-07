import re
import requests

from dadata import Dadata
from strsimpy.cosine import Cosine
from geopy.geocoders import ArcGIS

from flask import Flask
from flask_restful import Api, Resource

from webargs import fields
from webargs.flaskparser import use_args, parser, abort


cosine = Cosine(2)
arcgis_geolocator = ArcGIS()
_RE_COMBINE_WHITESPACE = re.compile(r'\s+|\n|\"|\t|/|\\+')
app = Flask(__name__)
api = Api(app)


# геокодер Yandex
class YandexGeocoder(Resource):
    yandex_args = {
        'token': fields.Str(required=True),
        'address': fields.Str(required=True)
    }
    
    @use_args(yandex_args, location='query')
    def get(self, args):
        address = _RE_COMBINE_WHITESPACE.sub(' ',args['address']).strip()
        url = 'https://geocode-maps.yandex.ru/1.x/?apikey='+args['token']+'&geocode='+address+'&format=json'
        r = requests.get(url)
        if r.status_code == 200:
            address_list = r.json()['response']['GeoObjectCollection']['featureMember']
            if address_list:
                long_lat = address_list[0]['GeoObject']['Point']['pos']
                lat = long_lat.split()[-1]
                lon = long_lat.split()[0]
                return {
                    'status_code': '200',
                    'lat': lat,
                    'lon': lon
                }
            else:
                return {
                'status_code': 400,
                'error': 'Невозможно геокодировать: '+address
            }


# геокодер ArcGis
class ArcGISGeocoder(Resource):
    arcgis_args = {
        'address': fields.Str(required=True)
    }
    
    @use_args(arcgis_args, location='query')
    def get(self, args):
        address = _RE_COMBINE_WHITESPACE.sub(' ',args['address']).strip()
        location = arcgis_geolocator.geocode(address)
        if not location:
            return {
                'status_code': 400,
                'error': 'Невозможно геокодировать: '+address
            }
        
        # get cosine of two strings
        p0 = cosine.get_profile(address)
        p1 = cosine.get_profile(location.address)
        similarity = cosine.similarity_profiles(p0, p1)
        if similarity >= 0.4:
            return {
                'status_code': '200',
                'lat': round(location.latitude, 6),
                'lon': round(location.longitude, 6)
            }
        else:
            return {
                'status_code': 400,
                'error': 'Невозможно геокодировать: '+address
            }


# гуокодер Dadata
class DadataGeocoder(Resource):
    dadata_args = {
        'token': fields.Str(required=True),
        'secret': fields.Str(required=True),
        'address': fields.Str(required=True)
    }
    
    @use_args(dadata_args, location='query')
    def get(self, args):
        address = _RE_COMBINE_WHITESPACE.sub(' ',args['address']).strip()
        dadata = Dadata(args['token'], args['secret'])
        dadata_result = dadata.clean(name='address', source=address)
        if dadata_result['geo_lat'] and dadata_result['geo_lon']:
            return {
                'status_code': '200',
                'lat': dadata_result['geo_lat'],
                'lon': dadata_result['geo_lon']
            }
        else:
            return {
                'status_code': 400,
                'error': 'Невозможно геокодировать: '+address
            }


# This error handler is necessary for usage with Flask-RESTful
@parser.error_handler
def handle_request_parsing_error(err, req, schema, *, error_status_code, error_headers):
    abort(error_status_code, errors=err.messages)


if __name__ == "__main__":
    api.add_resource(YandexGeocoder, "/yandex")
    api.add_resource(ArcGISGeocoder, "/arcgis")
    api.add_resource(DadataGeocoder, "/dadata")
    app.run(port=5001, debug=False)