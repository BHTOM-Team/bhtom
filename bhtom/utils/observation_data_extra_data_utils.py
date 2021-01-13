from astropy.io import ascii
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import DataProduct
from typing import Any, Dict, Optional
import json


FACILITY_NAME_KEY: str = "facility"
OBSERVATION_TIME_KEY: str = "observation_time"
OWNER_KEY: str = "owner"


class ObservationDatapointExtraData:
    def __init__(self,
                 facility_name: Optional[str] = None,
                 observation_time: Optional[str] = None,
                 owner: Optional[str] = None):
        self.__facility_name: Optional[str] = facility_name
        self.__observation_time: Optional[str] = observation_time
        self.__owner = owner

    @property
    def facility_name(self) -> Optional[str]:
        return self.__facility_name

    @property
    def observation_time(self) -> Optional[str]:
        return self.__observation_time

    @property
    def owner(self) -> Optional[str]:
        return self.__owner

    def to_json_str(self) -> str:
        data: Dict[str, str] = {}
        if self.__facility_name:
            data[FACILITY_NAME_KEY] = self.__facility_name

        # TODO: perhaps more observation time validation (e.g. no future datetimes)
        if self.__observation_time:
            data[OBSERVATION_TIME_KEY] = self.__observation_time

        if self.__owner:
            data[OWNER_KEY] = str(self.__owner)

        return json.dumps(data)


def decode_datapoint_extra_data(data: Dict[str, Any]) -> ObservationDatapointExtraData:
    return ObservationDatapointExtraData(facility_name=data.get(FACILITY_NAME_KEY, None),
                                         observation_time=data.get(OBSERVATION_TIME_KEY, None),
                                         owner=data.get(OWNER_KEY, None))


def get_facility_and_obs_time_for_spectroscopy_file(data_product: DataProduct) -> Optional[ObservationDatapointExtraData]:
    """
        Returns the facility name and observation time if provided in the comment section
        of the file
    """
    try:
        data = ascii.read(data_product.data.path)
    except InvalidFileFormatException:
        return None

    facility_name: Optional[str] = None
    date_obs: Optional[str] = None

    try:
        comments = data.meta.get('comments', [])
    except Exception as e:
        return None

    for comment in comments:
        if 'date-obs' in comment.lower():
            try:
                date_obs = comment.split(':')[1].strip()
            except IndexError:
                date_obs = None
        if 'facility' in comment.lower():
            try:
                facility_name = comment.split(':')[1].strip()
            except IndexError:
                facility_name = None

    return ObservationDatapointExtraData(facility_name=facility_name,
                                         observation_time=date_obs)
