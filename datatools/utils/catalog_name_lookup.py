from logging import Logger, getLogger
from typing import Dict, Optional

from astroquery.simbad import Simbad

import requests
from django.conf import settings
from lxml import html

logger: Logger = getLogger(__name__)
alert_name_keys: Dict[str, str] = settings.ALERT_NAME_KEYS


def get_tns_id_from_gaia_name(gaia_name: str) -> Optional[str]:
    try:
        alert_url: str = f'{settings.GAIA_ALERT_URL}/{gaia_name}'
        result = requests.get(alert_url)
        status_code: Optional[int] = getattr(result, 'status_code', None)

        if status_code == 200:
            tree = html.fromstring(result.content)
            tns_ids = tree.xpath("//dt[text()='TNS ID']/following::dd/a/text()")
            if tns_ids and len(tns_ids) > 0:
                return tns_ids[0]
        else:
            logger.error(f'Error when requesting the URL. Returned status code: {status_code}')

    except Exception as e:
        logger.error(f'Error while looking up TNS ID for {gaia_name}: {e}')
        return None


def get_gaia_ztf_names_for_tns_id(tns_id: str) -> Dict[str, str]:
    """
    Queries the TNS server and returns a dictionary with
    ztf_alert_name and gaia_alert_name, if found
    """
    try:
        target_url: str = f'{settings.TNS_OBJECT_URL}/{tns_id_to_url_slug(tns_id)}'

        logger.info(f'Requesting data from the TNS server for object with TNS_ID {tns_id} at the address {target_url}...')

        result = requests.get(target_url)
        status_code: Optional[int] = getattr(result, 'status_code', None)

        logger.debug(f'Request at {target_url} returned status code {status_code}')

        result_dict: Dict[str, str] = {}

        if status_code == 200:

            tree = html.fromstring(result.content)

            ztf_names = tree.xpath(tns_internal_name_xpath("ZTF"))
            if ztf_names and len(ztf_names) > 0:
                result_dict['ztf_alert_name'] = ztf_names[0]

            gaia_names = tree.xpath(tns_internal_name_xpath("GaiaAlerts"))
            if gaia_names and len(gaia_names) > 0:
                result_dict['gaia_alert_name'] = gaia_names[0]

            return result_dict
        else:
            logger.error(f'Error when requesting the URL on TNS server. Returned status code: {status_code}')
            return {}

    except Exception as e:
        logger.error(f'Error while looking up alert internal names on the TNS server: {e}')
        return {}


def query_simbad_for_names(identifier: str) -> Dict[str, str]:
    from astropy.table import Table
    import re

    try:
        logger.info(f'Querying Simbad for target {identifier}...')

        result_table: Optional[Table] = Simbad.query_objectids(object_name=identifier)
        result_dict: Dict[str] = {}

        if result_table:
            for row in result_table['ID']:
                print(row)
                if 'AAVSO' in row:
                    result_dict[alert_name_keys['AAVSO']] = re.sub(r'^AAVSO( )*', '', row)
                elif 'Gaia DR2' in row:
                    result_dict[alert_name_keys['GAIA DR2']] = re.sub(r'^Gaia( )*DR2( )*', '', row)

        return result_dict
    except Exception as e:
        logger.error(f'Error while querying Simbad for target {identifier}: {e}')
        return {}


def tns_id_to_url_slug(tns_id: str) -> str:
    import re

    return re.sub(r'^([A-Z])+( )*', '', tns_id)


def tns_internal_name_xpath(group_name: str) -> str:
    return f'//tr[td[@class="cell-groups" and text()="{group_name}"]]/td[@class="cell-internal_name"]/text()'


