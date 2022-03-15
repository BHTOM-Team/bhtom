import json
import requests

from typing import Any, Dict, Optional

from astropy import units as u
from astropy.coordinates import SkyCoord
from collections import OrderedDict
from django.conf import settings

from tom_catalogs.harvester import AbstractHarvester
from tom_common.exceptions import ImproperCredentialsException

from bhtom.exceptions.external_service import NoResultException

TNS_URL = 'https://www.wis-tns.org'
TNS_USER_AGENT = settings.TNS_USER_AGENT
NO_RESULT_ID: int = 110

try:
    TNS_API_KEY = settings.TNS_API_KEY
except (AttributeError, KeyError):
    TNS_API_KEY = ''


def get_reply_from_response(response: Dict[str, Any]) -> Dict[str, Any]:
    return response.get('data', {}).get('reply', {})


def get_name_message_id(reply: Dict[str, Any]) -> Optional[int]:
    try:
        message_id: Optional[int] = list(reply.get('name', {}).values())[0].get('message_id')
    except:
        message_id: Optional[int] = None
    return message_id


def get(term):
    # url = "https://www.wis-tns.org/api/get"

    get_url = TNS_URL + '/api/get/object'

    # change term to json format
    json_list = [("objname", term)]
    json_file = OrderedDict(json_list)

    # header with bot name and ID
    headers = {
        'User-Agent': TNS_USER_AGENT
    }

    # construct the list of (key,value) pairs
    get_data = [('api_key', (None, TNS_API_KEY)),
                ('data', (None, json.dumps(json_file)))]

    response = requests.post(get_url, files=get_data, headers=headers)
    response_data = json.loads(response.text)

    if 400 <= response_data.get('id_code') <= 403:
        raise ImproperCredentialsException('TNS: ' + str(response_data.get('id_message')))

    # If no object found:
    reply: Dict[str, Any] = get_reply_from_response(response_data)
    message_id: Optional[id] = get_name_message_id(reply)
    if message_id == NO_RESULT_ID:
        raise NoResultException(f'TNS: no results for {term}')

    return reply


class TNSHarvester(AbstractHarvester):
    """
    The ``TNSBroker`` is the interface to the Transient Name Server. For information regarding the TNS, please see
    https://wis-tns.weizmann.ac.il/.
    """

    name = 'TNS'

    def query(self, term):
        self.catalog_data = get(term)

    def to_target(self):
        target = super().to_target()
        target.type = 'SIDEREAL'
        target.name = (self.catalog_data.get('name_prefix', '') + self.catalog_data.get('objname', ''))
        c = SkyCoord('{0} {1}'.format(self.catalog_data.get('ra'), self.catalog_data.get('dec')), unit=(u.hourangle, u.deg))
        target.ra, target.dec = c.ra.deg, c.dec.deg
        return target
