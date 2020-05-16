import uuid
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, APITestCase, APIClient
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
        self.assertEqual(response.data['status'], 'I')
