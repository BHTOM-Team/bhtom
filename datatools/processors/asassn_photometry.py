import json
import mimetypes
import re
from typing import Optional

from astropy import units
from astropy.io import ascii
from astropy.time import Time, TimezoneInfo
from tom_dataproducts.data_processor import DataProcessor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_targets.models import Target
import logging

from datatools.utils.hjd_to_jd import hjd_to_jd


logger = logging.getLogger(__name__)


class ASASSNPhotometryProcessor(DataProcessor):

    def process_data(self, data_product):
        """
        Routes a photometry processing call to a method specific to a file-format.

        :param data_product: Photometric DataProduct which will be processed into the ASAS-SN format
        :type data_product: DataProduct

        :returns: python list of 2-tuples, each with a timestamp and corresponding data
        :rtype: list
        """

        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        if mimetype in self.PLAINTEXT_MIMETYPES:
            logger.debug('[ASAS-SN PHOTOMETRY] Starting to process ASAS-SN data...')
            photometry = self._process_photometry_from_plaintext(data_product)
            logger.debug('[ASAS-SN PHOTOMETRY] Photometry processed!')
            return [(datum.pop('timestamp'), json.dumps(datum)) for datum in photometry]
        else:
            raise InvalidFileFormatException('Unsupported file type')

    def _process_photometry_from_plaintext(self, data_product):
        """
        Processes the photometric data from a plaintext file into a list of dicts. File is read using astropy as
        specified in the below documentation. The file is expected to be a multi-column delimited file, with headers for
        time, magnitude, filter, and error.
        # http://docs.astropy.org/en/stable/io/ascii/read.html

        :param data_product: Photometric DataProduct which will be processed into a list of dicts
        :type data_product: DataProduct

        :returns: python list containing the photometric data from the DataProduct
        :rtype: list
        """

        photometry = []
        target: Target = data_product.target
        ra: float = target.ra
        dec: float = target.dec

        data = ascii.read(data_product.data.path)
        if len(data) < 1:
            logger.error('[ASAS-SN PHOTOMETRY] Empty table!')
            raise InvalidFileFormatException('Empty table or invalid file type')

        if 'hjd' in data.columns:
            hjd_index: str = 'hjd'
        elif 'HJD' in data.columns:
            hjd_index: str = 'HJD'
        else:
            raise InvalidFileFormatException('No hjd or HJD in data columns')

        if 'filter' in data.columns:
            filter_index: str = 'filter'
        elif 'Filter' in data.columns:
            filter_index: str = 'Filter'
        else:
            logger.error('[ASAS-SN PHOTOMETRY] No Filter in data!')
            raise InvalidFileFormatException('No filter or Filter in data columns')

        if 'mag err' in data.columns:
            mag_err_index: Optional[str] = 'mag err'
        elif 'mag_err' in data.columns:
            mag_err_index: Optional[str] = 'mag_err'
        else:
            mag_err_index: Optional[str] = None

        if 'camera' in data.columns:
            camera_index: Optional[str] = 'camera'
        elif 'Camera' in data.columns:
            camera_index: Optional[str] = 'Camera'
        else:
            camera_index: Optional[str] = None

        for datum in data:
            try:
                hjd: Time = datum[hjd_index]
                jd: Time = Time(hjd_to_jd(hjd, ra, dec)[0], format='jd')

                utc = TimezoneInfo(utc_offset=0 * units.hour)
                jd.format = 'datetime'
                value = {
                    'timestamp': jd.to_datetime(timezone=utc),
                    'magnitude': self._filter_non_numbers(str(datum['mag'])),
                    'filter': f'{datum[filter_index]}/ASAS-SN',
                    'jd': jd.jd,
                    'hjd': hjd
                }

                if camera_index:
                    value['camera'] = datum[camera_index]
                if mag_err_index:
                    value['error'] = self._filter_non_numbers(str(datum[mag_err_index]))
                photometry.append(value)
            except Exception as e:
                logger.error(f'[ASAS-SN PHOTOMETRY] Error {e} while processing datum')
                raise InvalidFileFormatException(f'Error while processing data: {e}')

        return photometry

    def _filter_non_numbers(self, number_str: str) -> float:
        return float(re.sub('[^0-9\.]', '', number_str))
