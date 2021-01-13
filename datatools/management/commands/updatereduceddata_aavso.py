from bhtom.harvesters.aavso_data_fetch import fetch_aavso_photometry
from .utils.result_messages import MessageStatus, encode_message
from .update_reduced_data import UpdateReducedDataCommand


class Command(UpdateReducedDataCommand):

    help = 'Downloads data for AAVSO'
    source_name = 'AAVSO'

    def update_function(self, target, user_id) -> str:
        dont_update_me: str = target.extra_fields.get('dont_update_me')
        aavso_name: str = target.extra_fields.get('aavso_name')

        if dont_update_me:
            return encode_message(MessageStatus.NONE,
                                  "Didn't update AAVSO data of %s because dont_update_me is set to True" % target.name)

        if aavso_name:
            result_df, result_status_code = fetch_aavso_photometry(target, requesting_user_id=user_id)
            if result_status_code == 200:
                return encode_message(MessageStatus.SUCCESS,
                                      "Updated AAVSO data for %s. Received %d datapoints" % (
                                      aavso_name, len(result_df.index)))
            else:
                return encode_message(MessageStatus.ERROR,
                                      "Couldn't connect to the AAVSO database- returned status code: %d" % result_status_code)
        else:
            return encode_message(MessageStatus.NONE,
                                  "No AAVSO name provided for %s" % target.name)


