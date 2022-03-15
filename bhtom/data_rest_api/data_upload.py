import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from tom_common.hooks import run_hook
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_targets.models import Target

from bhtom.middleware.hashtag_authentication_middleware import HashtagAuthentication
from bhtom.models import refresh_reduced_data_view, Instrument, Observatory, BHTomFits

logger = logging.getLogger(__name__)


class PhotometryUpload(APIView):
    """
    """
    authentication_classes = [HashtagAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):

        user = request.user

        hashtag: str = request.headers.get('hashtag')
        instrument = Instrument.objects.get(hashtag=hashtag)

        target_name: str = request.data.get('target')
        filter: str = request.data.get('filter')
        data_product_type: str = request.data.get('data_product_type')

        observatory = Observatory.objects.get(id=instrument.observatory_id.id)

        mjd: str = request.data.get('mjd')
        exp_time: str = request.data.get('exp_time')

        dry_run_str: str = request.data.get('dry_run', 'False')
        dry_run = True if dry_run_str == 'True' else False

        matching_radius: str = request.data.get('matching_radius', '2')
        comment: str = request.data.get('comment')

        file = request.FILES.get('files')

        time_threshold = timezone.now() - timedelta(days=1)
        fits_quantity = BHTomFits.objects.filter(start_time__gte=time_threshold).count()
        fits_quantity = fits_quantity * 10

        try:
            target: Target = Target.objects.get(name=target_name)
        except Target.DoesNotExist:
            return Response({'error': f'Target {target_name} does not exist'}, status=400)

        dp: DataProduct = DataProduct(
            target=target,
            data=file,
            product_id=None,
            data_product_type=data_product_type
        )
        dp.save()

        try:
            run_hook('data_product_post_upload',
                     dp, target, observatory,
                     filter, mjd, exp_time,
                     dry_run, matching_radius, comment,
                     user, fits_quantity,
                     hashtag=hashtag)

            run_data_processor(dp)

            # successful_uploads.append(str(dp).split('/')[-1])
            refresh_reduced_data_view()
        except Exception as e:
            ReducedDatum.objects.filter(data_product=dp).delete()
            dp.delete()
            return Response({'exception': str(e)}, status=500)

        return Response({'target': target_name,
                         'filter': filter})
