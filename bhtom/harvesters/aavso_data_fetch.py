from io import StringIO
from typing import List, Optional, Tuple

import pandas as pd
import requests as req
from astropy.time import Time
from django.conf import settings
from django.core.cache import cache
from tom_dataproducts.models import ReducedDatum
from tom_targets.models import Target

from bhtom.models import ReducedDatumExtraData
from bhtom.utils.observation_data_extra_data_utils import ObservationDatapointExtraData

accepted_valid_flags: List[str] = ['V']
filters: List[str] = ['V', 'I', 'R']
source_name: str = 'AAVSO'


def fetch_aavso_photometry(target: Target,
                           from_time: Optional[Time] = None,
                           to_time: Time = Time.now(),
                           delimiter: str = "~",
                           requesting_user_id: Optional[int] = None) -> Tuple[Optional[pd.DataFrame], Optional[int]]:
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
            save_row_to_db(target_id, row, settings.AAVSO_DATA_FETCH_URL, requesting_user_id)

        cache.set(f'{target_id}_aavso', result_df.JD.max())

        return result_df, result.status_code
    else:
        return None, status_code


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[df.obsType == 'CCD']\
        .loc[df.val.isin(accepted_valid_flags)]\
        .loc[df.band.isin(filters)]


def save_row_to_db(target_id: int,
                   row: pd.Series,
                   url: str,
                   requesting_user_id: Optional[int] = None):
    rd, _ = ReducedDatum.objects.get_or_create(
        data_type="photometry",
        source_name=source_name,
        source_location=url,
        timestamp=Time(row["JD"], format="jd").to_datetime(),
        value=to_json_value(row),
        target_id=target_id
    )

    obs_affil: str = row["obsAffil"]

    if obs_affil or requesting_user_id:
        rd_extra_data, _ = ReducedDatumExtraData.objects.update_or_create(
            reduced_datum=rd,
            defaults={'extra_data': ObservationDatapointExtraData(facility_name=obs_affil,
                                                                  owner_id=requesting_user_id).to_json_str()}
        )
    return rd


def to_json_value(row: pd.Series):
    import json
    return json.dumps({
        "magnitude": row["mag"],
        "filter": "AAVSO/%s" % row["band"],
        "error": row["uncert"]
    })
