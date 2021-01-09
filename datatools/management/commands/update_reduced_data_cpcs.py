from .update_reduced_data import UpdateReducedDataCommand
from .utils.result_messages import MessageStatus, encode_message

from bhtom.harvesters.cpcs_alerts_harvester import update_cpcs_lc


class Command(UpdateReducedDataCommand):

    help = 'Downloads data for ZTF Alerts'
    source_name = 'ZTF'

    def update_function(self, target, user_id) -> str:
        dont_update_me: str = target.extra_fields.get('dont_update_me')
        cpcs_name: str = target.extra_fields.get('calib_server_name')

        if dont_update_me:
            return encode_message(MessageStatus.INFO,
                                  "Didn't update CPCS data of %s because dont_update_me is set to True" % target.name)

        if cpcs_name:
            update_cpcs_lc(target)
            return encode_message(MessageStatus.SUCCESS,
                                  f'Updated CPCS data for {cpcs_name}')
        else:
            return encode_message(MessageStatus.INFO,
                                  "No Calib Server name provided for %s" % target.name)
