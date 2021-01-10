from django.core.management.base import BaseCommand
from tom_targets.models import Target
from bhtom.utils.aavso_data_fetch import fetch_aavso_photometry

from .utils.result_messages import MessageStatus, encode_message
from typing import Optional

class Command(BaseCommand):

    help = 'Downloads data for AAVSO'

    def add_arguments(self, parser):
        parser.add_argument('--target_id', help='Download data for a single target')
        parser.add_argument('--stdout', help='Stdout stream')
        parser.add_argument('--user_id', help='ID of the user requesting the data download')

    def handle(self, *args, **options) -> str:
        user_id = options['user_id']
        if options['target_id']:
            target_id = options['target_id']
            try:
                target: Target = Target.objects.get(pk=target_id)
                return update_aavso_for_single_target(target, user_id)
            except Exception as e:
                return encode_message(MessageStatus.ERROR,
                                      "There was a problem while updating AAVSO data for %s: %s" % (getattr(target, 'name', ""), e))
        else:
            for target in Target.objects.all():
                try:
                    print(update_aavso_for_single_target(target, user_id))
                except Exception as e:
                    print("Problem with updating AAVSO data for the target %d: %s" % (target.pk, e))
            return encode_message(MessageStatus.SUCCESS,
                                  "Updated AAVSO data for all targets")


def update_aavso_for_single_target(target: Target,
                                   user_id: Optional[int]) -> str:
    dont_update_me: str = target.extra_fields.get('dont_update_me')
    aavso_name: str = target.extra_fields.get('aavso_name')

    if dont_update_me:
        return encode_message(MessageStatus.INFO,
                              "Didn't update AAVSO data of %s because dont_update_me is set to True" % target.name)

    if aavso_name:
        result_df, result_status_code = fetch_aavso_photometry(target, requesting_user_id=user_id)
        if result_status_code == 200:
            return encode_message(MessageStatus.SUCCESS,
                                  "Updated AAVSO data for %s. Received %d datapoints" % (aavso_name, len(result_df.index)))
        else:
            return encode_message(MessageStatus.ERROR,
                                  "Couldn't connect to the AAVSO database- returned status code: %d" % result_status_code)
    else:
        return encode_message(MessageStatus.INFO,
                              "No AAVSO name provided for %s" % target.name)

