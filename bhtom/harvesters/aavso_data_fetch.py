from io import StringIO
from typing import List, Optional, Tuple
import logging

import pandas as pd
import requests as req
from astropy.time import Time, TimezoneInfo
from django.conf import settings
from django.core.cache import cache
from tom_dataproducts.models import ReducedDatum
from tom_targets.models import Target

from bhtom.models import ReducedDatumExtraData, refresh_reduced_data_view
from bhtom.utils.coordinate_utils import update_sun_separation
from bhtom.utils.observation_data_extra_data_utils import ObservationDatapointExtraData

logger = logging.getLogger(__name__)

accepted_valid_flags: List[str] = ['V', 'Z']
filters: List[str] = ['V', 'I', 'R']
source_name: str = 'AAVSO'

timezone_info: TimezoneInfo = TimezoneInfo()


def fetch_aavso_photometry(target: Target,
                           from_time: Optional[Time] = None,
                           to_time: Time = Time.now(),
                           delimiter: str = "~") -> Tuple[Optional[pd.DataFrame], Optional[int]]:
    update_sun_separation(target)
    target_name: str = target.name
    target_id: int = target.pk

    params = {
        "view": "api.delim",
        "ident": target_name,
        "tojd": to_time.jd,
        "fromjd": from_time.jd if from_time else 0,
        "delimiter": delimiter
    }
    result = req.get(settings.AAVSO_DATA_FETCH_URL, params=params)
    status_code: Optional[int] = getattr(result, 'status_code', None)

    if status_code and getattr(result, 'text', None):
        buffer: StringIO = StringIO(str(result.text))
        result_df: pd.DataFrame = filter_data(pd.read_csv(buffer,
                                                          sep=delimiter,
                                                          index_col=False,
                                                          error_bad_lines=False))

        for i, row in result_df.iterrows():
            save_row_to_db(target_id, row, settings.AAVSO_DATA_FETCH_URL)

        cache.set(f'{target_id}_aavso', result_df.JD.max())
        refresh_reduced_data_view()

        return result_df, result.status_code
    else:
        return None, status_code


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[df.obsType == 'CCD']\
        .loc[df.val.isin(accepted_valid_flags)]\
        .loc[df.band.isin(filters)]


def save_row_to_db(target_id: int,
                   row: pd.Series,
                   url: str):
    rd, _ = ReducedDatum.objects.get_or_create(
        data_type="photometry",
        source_name=source_name,
        source_location=url,
        timestamp=Time(row["JD"], format="jd", scale="utc").to_datetime(timezone=timezone_info),
        value=to_json_value(row),
        target_id=target_id
    )

    obs_affil: str = row["obsAffil"]
    obs_name: str = row["obsName"]

    if obs_affil or obs_name:

        rd_extra_data, _ = ReducedDatumExtraData.objects.update_or_create(
            reduced_datum=rd,
            defaults={'extra_data': ObservationDatapointExtraData(facility_name=obs_affil,
                                                                  owner=obs_name).to_json_str()}
        )
        logger.info('ReducedDatumExtraData from AAVSO ' + obs_name)
    return rd


def to_json_value(row: pd.Series):
    import json
    return json.dumps({
        "magnitude": row["mag"],
        "filter": "%s/AAVSO" % row["band"],
        "error": row["uncert"],
        "jd": row["JD"]
    })
