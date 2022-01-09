import json
import math
import operator
from tempfile import NamedTemporaryFile
from typing import Any, List, Optional, Tuple
from astropy.time import Time

import pandas as pd

from django.conf import settings
from tom_dataproducts.processors.data_serializers import SpectrumSerializer
from tom_targets.models import Target

from bhtom.models import ViewReducedDatum
from .observation_data_extra_data_utils import decode_datapoint_extra_data, ObservationDatapointExtraData, OWNER_KEY
from ..templatetags.photometry_tags import FACILITY_KEY

SPECTROSCOPY: str = "spectroscopy"


def load_datum_json(json_values):
    if json_values:
        if type(json_values) is dict:
            return json_values
        else:
            return json.loads(json_values.replace("\'", "\""))
    else:
        return {}


def get_observation_facility(datum: ViewReducedDatum) -> Optional[str]:
    try:
        # If the reduced datum is from an observation, then
        # the data product object is linked to an observation record
        # which contains information about the facility
        if datum.observation_record_facility:
            return datum.observation_record_facility

        # Then, check in reduced datum extra data
        # Some sources might save additional data, such as
        # the facility name, in the reduced datum extra data
        # There should be just one extra data object, as
        # the reduced datum extra data has reduced datum as the primary key.
        return load_datum_json(datum.rd_extra_data).get(FACILITY_KEY,
                                                        load_datum_json(datum.dp_extra_data).get(FACILITY_KEY, ""))
    except:
        return None


def get_observer_name(datum: ViewReducedDatum) -> Optional[str]:
    try:
        # First, check in reduced datum extra data
        # Some sources might save additional data, such as
        # the facility name, in the reduced datum extra data
        # There should be just one extra data object, as
        # the reduced datum extra data has reduced datum as the primary key.
        return load_datum_json(datum.rd_extra_data).get(OWNER_KEY,
                                                        load_datum_json(datum.dp_extra_data).get(OWNER_KEY, ""))
    except:
        return None


def decode_owner(extra_data_json_str: str) -> Optional[str]:
    extra_data: Optional[ObservationDatapointExtraData] = decode_datapoint_extra_data(json.loads(extra_data_json_str))
    return getattr(extra_data, 'owner', None)


def get_spectroscopy_observation_time_jd(reduced_datum: ViewReducedDatum) -> Optional[float]:
    from dateutil import parser
    from datetime import datetime
    from astropy.time import Time
    # Observation time might be included in the file, if spectrum is from an ASCII file.

    if reduced_datum.dp_extra_data:
        extra_data: Optional[ObservationDatapointExtraData] = decode_datapoint_extra_data(
            json.loads(reduced_datum.dp_extra_data))
        if getattr(extra_data, 'observation_time', None):
            try:
                observation_time: datetime = parser.parse(extra_data.observation_time)
                return Time(observation_time).jd
            except ValueError:
                return None
    return None


def get_photometry_data_table(target_id: int) -> Tuple[List[List[str]], List[str]]:
    from astropy.time import Time

    target: Target = Target.objects.get(pk=target_id)
    datums: ViewReducedDatum = ViewReducedDatum.objects.filter(target=target,
                                                               data_type__in=[
                                                                   settings.DATA_PRODUCT_TYPES['photometry'][0],
                                                                   settings.DATA_PRODUCT_TYPES['photometry_asassn'][0]])

    columns: List[str] = ['JD', 'Magnitude', 'Error', 'Facility', 'Filter', 'Owner']
    data: List[List[Any]] = []

    for datum in datums:
        values = json.loads(datum.value)

        data.append([Time(datum.timestamp).jd,
                     values.get('magnitude'),
                     values.get('error'),
                     get_observation_facility(datum),
                     values.get('filter'),
                     get_observer_name(datum)])

    return data, columns


def get_photometry_stats(target_id: int) -> Tuple[List[List[str]], List[str]]:
    data, columns = get_photometry_data_table(target_id)

    df: pd.DataFrame = pd.DataFrame(data=data,
                                    columns=columns)

    # For now, ignore anything after the ',' character if present
    # This is because sometimes Facility is in form "Facility, Observer"
    # and we only want to take the Facility name
    # If Facility is not present, then fill it with Owner value
    # If the Owner is blank too, fill it with "Unspecified"
    df['Facility'] = df['Facility'] \
        .apply(lambda x: None if (isinstance(x, float) and math.isnan(x)) else x) \
        .fillna(df['Owner']) \
        .fillna('Unspecified') \
        .apply(lambda x: str(x).split(',', 1)[0])

    facilities = df['Facility'].unique()

    columns: List[str] = ['Facility', 'Filters', 'Data_points']
    stats: List[List[Any]] = []

    for facility in facilities:
        datapoints = len(df[df['Facility'] == facility].index)
        filters = df[df['Facility'] == facility]['Filter'].unique()
        stats.append([facility, ", ".join(filters), datapoints])

    stats = sorted(stats, key=operator.itemgetter(2), reverse=True)

    return stats, columns


def save_data_to_temporary_file(data: List[List[Any]],
                                columns: List[str],
                                filename: str,
                                sort_by: str = 'JD',
                                sort_by_asc: bool = True) -> Tuple[NamedTemporaryFile, str]:
    df: pd.DataFrame = pd.DataFrame(data=data,
                                    columns=columns).sort_values(by=sort_by, ascending=sort_by_asc)

    tmp: NamedTemporaryFile = NamedTemporaryFile(mode="w+",
                                                 suffix=".csv",
                                                 prefix=filename,
                                                 delete=False)

    with open(tmp.name, 'w') as f:
        df.to_csv(f.name,
                  index=False,
                  sep=';')

    return tmp, filename


def save_data_to_latex_table(data: List[List[Any]],
                             columns: List[str],
                             filename: str) -> Tuple[NamedTemporaryFile, str]:
    from .latex_utils import data_to_latex_table

    latex_table_str: str = data_to_latex_table(data=data, columns=columns, filename=filename)

    tmp: NamedTemporaryFile = NamedTemporaryFile(mode="w+",
                                                 suffix=".csv",
                                                 prefix=filename,
                                                 delete=False)

    with open(tmp.name, 'w') as f:
        f.write(latex_table_str)

    return tmp, filename


def get_photometry_stats_latex(target_id: int) -> Tuple[NamedTemporaryFile, str]:
    target: Target = Target.objects.get(pk=target_id)

    data, columns = get_photometry_stats(target_id)

    filename: str = "target_%s_photometry_stats.tex" % target.name

    return save_data_to_latex_table(data, columns, filename)


def get_photometry_data_stats(target_id: int) -> Tuple[NamedTemporaryFile, str]:
    target: Target = Target.objects.get(pk=target_id)

    stats, columns = get_photometry_stats(target_id)

    filename: str = "target_%s_photometry_stats.csv" % target.name

    return save_data_to_temporary_file(stats, columns, filename, 'Data_points', False)


def save_photometry_data_for_target_to_csv_file(target_id: int) -> Tuple[NamedTemporaryFile, str]:
    target: Target = Target.objects.get(pk=target_id)

    data, columns = get_photometry_data_table(target_id)

    filename: str = "target_%s_photometry.csv" % target.name

    return save_data_to_temporary_file(data, columns, filename)


def save_spectroscopy_data_for_target_to_csv_file(target_id: int) -> Tuple[NamedTemporaryFile, str]:
    from astropy.time import Time

    target: Target = Target.objects.get(pk=target_id)
    datums: ViewReducedDatum = ViewReducedDatum.objects.filter(target=target,
                                                               data_type=settings.DATA_PRODUCT_TYPES['spectroscopy'][0])

    columns: List[str] = ['JD', 'Flux', 'Wavelength', 'Flux Units', 'Wavelength Units', 'Facility', 'Owner']
    data: List[List[Any]] = []

    for datum in datums:
        values = json.loads(datum.value)
        deserialized = SpectrumSerializer().deserialize(datum.value)

        file_jd: Optional[float] = get_spectroscopy_observation_time_jd(datum)
        if file_jd:
            jd: float = file_jd
        else:
            jd: float = Time(datum.timestamp).jd

        flux_units: str = values.get('photon_flux_units')
        wavelength_units: str = values.get('wavelength_units')
        observation_facility: str = get_observation_facility(datum)
        observer_name: str = get_observer_name(datum)

        data.append([jd,
                     deserialized.flux.value,
                     deserialized.wavelength.value,
                     flux_units,
                     wavelength_units,
                     observation_facility,
                     observer_name])

    filename: str = "target_%s_spectroscopy.csv" % target.name

    return save_data_to_temporary_file(data, columns, filename)
