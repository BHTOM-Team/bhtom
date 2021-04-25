import json
from tempfile import NamedTemporaryFile
from typing import Any, List, Optional, Tuple

import pandas as pd
from django.conf import settings
from tom_dataproducts.processors.data_serializers import SpectrumSerializer
from tom_targets.models import Target

from bhtom.models import ViewReducedDatum
from .observation_data_extra_data_utils import decode_datapoint_extra_data, ObservationDatapointExtraData

SPECTROSCOPY: str = "spectroscopy"


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
        if datum.rd_extra_data:
            facility: Optional[str] = decode_facility_name(datum.rd_extra_data)
            if facility:
                return facility

        if datum.dp_extra_data:
            facility: Optional[str] = decode_facility_name(datum.dp_extra_data)
            if facility:
                return facility
    except:
        return None


def decode_facility_name(extra_data_json_str: str) -> Optional[str]:
    extra_data: Optional[ObservationDatapointExtraData] = decode_datapoint_extra_data(json.loads(extra_data_json_str))
    return getattr(extra_data, 'facility_name', None)


def get_observer_name(datum: ViewReducedDatum) -> Optional[str]:
    try:
        # First, check in reduced datum extra data
        # Some sources might save additional data, such as
        # the facility name, in the reduced datum extra data
        # There should be just one extra data object, as
        # the reduced datum extra data has reduced datum as the primary key.
        if datum.rd_extra_data:
            facility: Optional[str] = decode_owner(datum.rd_extra_data)
            if facility:
                return facility

        if datum.dp_extra_data:
            facility: Optional[str] = decode_owner(datum.dp_extra_data)
            if facility:
                return facility
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
        extra_data: Optional[ObservationDatapointExtraData] = decode_datapoint_extra_data(json.loads(reduced_datum.dp_extra_data))
        if getattr(extra_data, 'observation_time', None):
            try:
                observation_time: datetime = parser.parse(extra_data.observation_time)
                return Time(observation_time).jd
            except ValueError:
                return None
    return None


def save_data_to_temporary_file(data: List[List[Any]],
                                columns: List[str],
                                filename: str,
                                sort_by: str = 'JD') -> Tuple[NamedTemporaryFile, str]:
    df: pd.DataFrame = pd.DataFrame(data=data,
                                    columns=columns).sort_values(by=sort_by)

    tmp: NamedTemporaryFile = NamedTemporaryFile(mode="w+",
                                                 suffix=".csv",
                                                 prefix=filename,
                                                 delete=False)

    with open(tmp.name, 'w') as f:
        df.to_csv(f.name,
                  index=False)

    return tmp, filename


def get_photometry_data_stats(target_id: int) -> Tuple[NamedTemporaryFile, str]:
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

    df: pd.DataFrame = pd.DataFrame(data=data,
                                    columns=columns).sort_values(by='JD')

    # For now, ignore anything after the ',' character if present
    # This is because sometimes Facility is in form "Facility, Observer"
    # and we only want to take the Facility name
    df['Facility'] = df['Facility'].apply(lambda x: x.split(',', 1)[0].replace(',', ''))

    facilities = df['Facility'].unique()

    columns: List[str] = ['Facility', 'Filters', 'Datapoints']
    stats: List[List[Any]] = []

    for facility in facilities:
        datapoints = len(df[df['Facility'] == facility].index)
        filters = df[df['Facility'] == facility]['Filter'].unique()
        stats.append([facility, ", ".join(filters), datapoints])

    filename: str = "target_%s_photometry_stats.csv" % target.name

    return save_data_to_temporary_file(stats, columns, filename, 'Datapoints')


def save_photometry_data_for_target_to_csv_file(target_id: int) -> Tuple[NamedTemporaryFile, str]:
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
