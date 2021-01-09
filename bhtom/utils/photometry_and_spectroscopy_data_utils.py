import json
from django.conf import settings
from django.contrib.auth.models import User
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.processors.data_serializers import SpectrumSerializer
from tom_observations.models import ObservationRecord
from tom_targets.models import Target
from tempfile import NamedTemporaryFile

from bhtom.models import BHTomData, BHTomFits, Instrument, Observatory, ReducedDatumExtraData
from .data_product_types import DataProductType
from .observation_data_extra_data_utils import decode_datapoint_extra_data, ObservationDatapointExtraData
import pandas as pd
import json

from typing import Any, List, Optional, Tuple

SPECTROSCOPY: str = "spectroscopy"


def get_observation_facility(datum: ReducedDatum) -> Optional[str]:
    try:
        # First, check in reduced datum extra data
        # Some sources might save additional data, such as
        # the facility name, in the reduced datum extra data
        # There should be just one extra data object, as
        # the reduced datum extra data has reduced datum as the primary key.
        extra_data: Optional[ObservationDatapointExtraData] = get_reduced_datum_extra_data(datum)
        facility_name: Optional[str] = getattr(extra_data, 'facility_name', None)
        if facility_name:
            return facility_name

        data_product: DataProduct = getattr(datum, 'data_product', None)

        if data_product is None:
            # If there is no data product associated with the datum,
            # then it's from an alert broker
            return None

        # If the reduced datum is from an observation, then
        # the data product object is linked to an observation record
        # which contains information about the facility
        observation_record: Optional[ObservationRecord] = getattr(data_product,
                                                                  'observation_record',
                                                                  None)
        if observation_record:
            return observation_record.facility
        else:
            # If there is no observation record, then the reduced datum
            # is from a file uploaded by the user.

            if data_product.data_product_type == DataProductType.SPECTROSCOPY:
                # Spectroscopy data product uploaded from the user can contain facility information in extra data
                extra_data: Optional[ObservationDatapointExtraData] = get_spectroscopy_extra_data(data_product)
                if extra_data:
                    return extra_data.facility_name
            else:
                # If the data is not spectroscopic, a bhtom_fits object can exist
                bhtom_fits: Optional[BHTomFits] = BHTomFits.objects.filter(dataproduct_id=data_product.pk)
                instrument: Optional[Instrument] = getattr(bhtom_fits,
                                                           'instrument_id',
                                                           None)
                observatory: Optional[Observatory] = getattr(instrument,
                                                             'observatory_id',
                                                             None)
                return observatory.obsName

    except:
        return None


def get_username(datum: ReducedDatum) -> Optional[str]:
    try:
        # First, check in reduced datum extra data
        # Some sources might save additional data, such as
        # owner user, in the reduced datum extra data
        # There should be just one extra data object, as
        # the reduced datum extra data has reduced datum as the primary key.
        extra_data: Optional[ObservationDatapointExtraData] = get_reduced_datum_extra_data(datum)
        if getattr(extra_data, 'owner_id', None):
            user: Optional[User] = User.objects.get(pk=int(extra_data.owner_id))

            # Check if the user with given pk exists
            if user:
                return user.username

        # If there is no extra data for the reduced datum,
        # check if it belongs to a data product (e.g. is from a photometry CSV file)
        data_product: DataProduct = getattr(datum, 'data_product', None)
        if data_product is None:
            return None

        # If the datum is from observation or a file,
        # then an user is assigned to it and
        # there exists a BHTomData object
        bhtom_data: Optional[BHTomData] = BHTomData.objects.get(dataproduct_id=data_product.pk)
        user_id: Optional[User] = getattr(bhtom_data, 'user_id', None)
        return getattr(user_id, 'username', None)
    except:
        return None


def get_spectroscopy_extra_data(data_product: DataProduct) -> Optional[ObservationDatapointExtraData]:
    if data_product.data_product_type != DataProductType.SPECTROSCOPY:
        return None
    else:
        extra_data = getattr(data_product, 'extra_data', None)
        if extra_data:
            extra_data_json = json.loads(extra_data)
            return decode_datapoint_extra_data(extra_data_json)
        else:
            return None


def get_reduced_datum_extra_data(reduced_datum: ReducedDatum) -> Optional[ObservationDatapointExtraData]:
    extra_data_str: Optional[str] = getattr(ReducedDatumExtraData.objects.filter(reduced_datum=reduced_datum).first(),
                                            'extra_data',
                                            None)
    if extra_data_str:
        return decode_datapoint_extra_data(json.loads(extra_data_str))
    else:
        return None


def get_spectroscopy_observation_time_jd(reduced_datum: ReducedDatum) -> Optional[float]:
    from dateutil import parser
    from datetime import datetime
    from astropy.time import Time
    # Observation time might be included in the file, if spectrum is from an ASCII file.

    data_product: DataProduct = reduced_datum.data_product
    if data_product:
        extra_data: Optional[ObservationDatapointExtraData] = get_spectroscopy_extra_data(data_product)
        if getattr(extra_data, 'observation_time', None):
            try:
                observation_time: datetime = parser.parse(extra_data.observation_time)
                return Time(observation_time).jd
            except ValueError:
                return None
    return None


def save_data_to_temporary_file(data: List[List[Any]],
                                columns: List[str],
                                filename: str) -> Tuple[NamedTemporaryFile, str]:
    df: pd.DataFrame = pd.DataFrame(data=data,
                                    columns=columns).sort_values(by='JD')

    tmp: NamedTemporaryFile = NamedTemporaryFile(mode="w+",
                                                 suffix=".csv",
                                                 prefix=filename,
                                                 delete=False)

    with open(tmp.name, 'w') as f:
        df.to_csv(f.name,
                  index=False)

    return tmp, filename


def save_photometry_data_for_target_to_csv_file(target_id: int) -> Tuple[NamedTemporaryFile, str]:
    from astropy.time import Time

    target: Target = Target.objects.get(pk=target_id)
    datums: ReducedDatum = ReducedDatum.objects.filter(target=target,
                                                       data_type=settings.DATA_PRODUCT_TYPES['photometry'][0])

    columns: List[str] = ['JD', 'Magnitude', 'Error', 'Facility', 'Filter', 'Owner']
    data: List[List[Any]] = []

    for datum in datums:
        values = json.loads(datum.value)

        data.append([Time(datum.timestamp).jd,
                     values.get('magnitude'),
                     values.get('error'),
                     get_observation_facility(datum),
                     values.get('filter'),
                     get_username(datum)])

    filename: str = "target_%s_photometry.csv" % target.name

    return save_data_to_temporary_file(data, columns, filename)


def save_spectroscopy_data_for_target_to_csv_file(target_id: int) -> Tuple[NamedTemporaryFile, str]:
    from astropy.time import Time

    target: Target = Target.objects.get(pk=target_id)
    datums: ReducedDatum = ReducedDatum.objects.filter(target=target,
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
        username: str = get_username(datum)

        data.append([jd,
                     deserialized.flux.value,
                     deserialized.wavelength.value,
                     flux_units,
                     wavelength_units,
                     observation_facility,
                     username])

    filename: str = "target_%s_spectroscopy.csv" % target.name

    return save_data_to_temporary_file(data, columns, filename)