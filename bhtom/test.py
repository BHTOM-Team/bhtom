import uuid
import unittest
from django.test import TestCase
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, APITestCase, APIClient
from .utils.coordinate_utils import fill_galactic_coordinates
from tom_targets.models import Target
from bhtom.views import result_fits

class UploadFITSTestCase(APITestCase):

    def setUp(self) -> None:
        super().setUp()
        import astropy.io.fits as pyfits
        from io import BytesIO
        # Create in-memory FITS file
        self.fd = BytesIO()
        prihdr = pyfits.Header()
        prihdr['COMMENT'] = "ccphotd test file"
        prihdu = pyfits.PrimaryHDU(header=prihdr)
        prihdu.writeto(self.fd)

    def test_FITS_update(self):
        self.fd.seek(0)
        file = SimpleUploadedFile('test.dat', self.fd.read(),
                                  content_type='multipart/form-data')
        client = APIClient()
        response = client.patch('/result/d810efe3cd824c5aac94959000de3dff',
                               {
                                   "fits_id": 'd810efe3cd824c5aac94959000de3dff',
                                   "status": 'I',
                                   "ccdphot_result": file,
                               })
        self.assertEqual(response.status_code, 301)
        # self.assertEqual(response.data['status'], 'I')


class TestGalacticCoordsAutomaticFillIn(TestCase):
    def test_dont_fill_in_if_galactic_coords_passed(self):
        target: Target = Target(name='Test',
                                ra=10.00,
                                dec=12.00,
                                galactic_lat=15.00,
                                galactic_lng=15.00)
        fill_galactic_coordinates(target)
        self.assertAlmostEqual(target.galactic_lat, 15.00)
        self.assertAlmostEqual(target.galactic_lng, 15.00)

    def test_fill_in_if_galactic_coords_not_passed(self):
        target: Target = Target(name='Test',
                                ra=10.00,
                                dec=12.00,
                                galactic_lat=None,
                                galactic_lng=None)
        fill_galactic_coordinates(target)
        self.assertAlmostEqual(target.galactic_lng, 118.50, delta=1e-2)
        self.assertAlmostEqual(target.galactic_lat, -50.77, delta=1e-2)

    def test_dont_fill_in_if_ra_not_passed(self):
        target: Target = Target(name='Test',
                                ra=None,
                                dec=12.00,
                                galactic_lat=None,
                                galactic_lng=None)
        fill_galactic_coordinates(target)
        self.assertIsNone(target.galactic_lng)
        self.assertIsNone(target.galactic_lat)

    def test_dont_fill_in_if_dec_not_passed(self):
        target: Target = Target(name='Test',
                                ra=12.00,
                                dec=None,
                                galactic_lat=None,
                                galactic_lng=None)
        fill_galactic_coordinates(target)
        self.assertIsNone(target.galactic_lng)
        self.assertIsNone(target.galactic_lat)

    def test_dont_fill_in_if_ra_and_dec_not_passed(self):
        target: Target = Target(name='Test',
                                ra=None,
                                dec=None,
                                galactic_lat=None,
                                galactic_lng=None)
        fill_galactic_coordinates(target)
        self.assertIsNone(target.galactic_lng)
        self.assertIsNone(target.galactic_lat)

    def test_fill_in_if_galactic_lng_not_passed(self):
        target: Target = Target(name='Test',
                                ra=10.00,
                                dec=12.00,
                                galactic_lat=1.00,
                                galactic_lng=None)
        fill_galactic_coordinates(target)
        self.assertAlmostEqual(target.galactic_lng, 118.50, delta=1e-2)
        self.assertAlmostEqual(target.galactic_lat, -50.77, delta=1e-2)

    def test_fill_in_if_galactic_lat_not_passed(self):
        target: Target = Target(name='Test',
                                ra=10.00,
                                dec=12.00,
                                galactic_lat=None,
                                galactic_lng=1.00)
        fill_galactic_coordinates(target)
        self.assertAlmostEqual(target.galactic_lng, 118.50, delta=1e-2)
        self.assertAlmostEqual(target.galactic_lat, -50.77, delta=1e-2)
