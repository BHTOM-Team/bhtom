from .update_reduced_data import UpdateReducedDataCommand
from .utils.result_messages import MessageStatus, encode_message

from bhtom.harvesters.gaia_alerts_harvester import update_gaia_lc


class Command(UpdateReducedDataCommand):

    help = 'Downloads data for Gaia Alerts'
    source_name = 'Gaia Alerts'

    def update_function(self, target, user_id) -> str:
        dont_update_me: str = target.extra_fields.get('dont_update_me')
        gaia_name: str = target.extra_fields.get('gaia_alert_name')

        if dont_update_me:
            return encode_message(MessageStatus.NONE,
                                  "Didn't update Gaia Alerts data of %s because dont_update_me is set to True" % target.name)

        if gaia_name:
            update_gaia_lc(target, user_id)
            return encode_message(MessageStatus.SUCCESS,
                                  f'Updated Gaia Alerts data for {gaia_name}')
        else:
            return encode_message(MessageStatus.NONE,
                                  "No Gaia Alerts name provided for %s" % target.name)
