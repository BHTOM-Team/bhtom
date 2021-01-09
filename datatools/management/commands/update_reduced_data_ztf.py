from .update_reduced_data import UpdateReducedDataCommand
from .utils.result_messages import MessageStatus, encode_message

from bhtom.harvesters.ztf_alerts_harvester import update_ztf_lc


class Command(UpdateReducedDataCommand):

    help = 'Downloads data for ZTF Alerts'
    source_name = 'ZTF'

    def update_function(self, target, user_id) -> str:
        dont_update_me: str = target.extra_fields.get('dont_update_me')
        ztf_name: str = target.extra_fields.get('ztf_alert_name')

        if dont_update_me:
            return encode_message(MessageStatus.INFO,
                                  "Didn't update ZTF data of %s because dont_update_me is set to True" % target.name)

        if ztf_name:
            update_ztf_lc(target)
            return encode_message(MessageStatus.SUCCESS,
                                  f'Updated ZTF data for {ztf_name}')
        else:
            return encode_message(MessageStatus.INFO,
                                  "No ZTF name provided for %s" % target.name)
