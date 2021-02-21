import json
import mimetypes

from astropy import units
from astropy.io import ascii
from astropy.time import Time, TimezoneInfo
from tom_dataproducts.data_processor import DataProcessor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_targets.models import Target

from datatools.utils.hjd_to_jd import hjd_to_jd


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
            photometry = self._process_photometry_from_plaintext(data_product)
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
            raise InvalidFileFormatException('Empty table or invalid file type')

        for datum in data:
            try:
                hjd: Time = datum['hjd']
                jd: Time = Time(hjd_to_jd(hjd, ra, dec)[0], format='jd')

                utc = TimezoneInfo(utc_offset=0 * units.hour)
                jd.format = 'datetime'
                value = {
                    'timestamp': jd.to_datetime(timezone=utc),
                    'magnitude': datum['mag'],
                    'camera': datum['camera'],
                    'filter': f'{datum["filter"]}/ASAS-SN',
                    'error': datum['mag err'],
                    'jd': jd.jd,
                    'hjd': hjd
                }
                photometry.append(value)
            except Exception as e:
                print(e)

        return photometry
