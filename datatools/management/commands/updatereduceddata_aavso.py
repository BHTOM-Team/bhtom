from django.core.management.base import BaseCommand
from tom_targets.models import Target
from bhtom.utils.aavso_data_fetch import fetch_aavso_photometry

class Command(BaseCommand):

    help = 'Downloads data for AAVSO'

    def add_arguments(self, parser):
        parser.add_argument('--target_id', help='Download data for a single target')
        parser.add_argument('--stdout', help='Stdout stream')

    def handle(self, *args, **options):
        if options['target_id']:
            target_id = options['target_id']
            print("Fetching AAVSO data for a single target: %s"%target_id)
            try:
                target: Target = Target.objects.get(pk=target_id)
                update_aavso_for_single_target(target)
                return ('Light curve of %s updated') % (target.name)
            except Exception as e:
                return "There was a problem updating %s: %s" % (getattr(target, 'name', ""), e)
        else:
            for target in Target.objects.all():
                try:
                    update_aavso_for_single_target(target)
                except:
                    print("Problem with updating AAVSO data for the tarfet %d"%target.pk)
            return "Updated AAVSO data for all targets"


def update_aavso_for_single_target(target: Target) -> str:
    dont_update_me = target.targetextra_set.get(key='dont_update_me').value

    if dont_update_me == 'True':
        return "Didn't update photometry data of %s because dont_update_me=True" % target.name

    fetch_aavso_photometry(target)

