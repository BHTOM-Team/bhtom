from django.core.management.base import BaseCommand
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

from myapp.harvesters import gaia_alerts_harvester

class Command(BaseCommand):

    help = 'Downloads data for Gaia Alerts'

    def add_arguments(self, parser):
        parser.add_argument('--target_id', help='Download data for a single target')
        parser.add_argument('--stdout', help='Stdout stream') #not using ?

    def handle(self, *args, **options):
        if options['target_id']:
            target_id = options['target_id']
            print("updating single ",target_id)
            try:
                target_object = Target.objects.get(pk=target_id)
                gaia = target_object.targetextra_set.get(key='gaia_alert_name').value
                gaia_alerts_harvester.update_gaia_lc(target_object, gaia)
                updateme = (target_object.targetextra_set.get(key='update_me').value)
                if (updateme=="False"): 
                    return ('Light curve of %s not updated because of update_me flag')%(gaia)
                else:
                    return ('Light curve of %s updated')%(gaia)
                print("UPDATED lc of ",gaia)
            except Exception as e:
               print("target ",target_id,' not updated, probably no gaia_alert_name provided for this target')  
               print(e)
               return ('Problems updating %s')%(target_id)
        else:
            # call_command('updatereduceddata', stdout=out)
            print("updating many ")

            for t in Target.objects.all():
                try:
                    gaia = t.targetextra_set.get(key='gaia_alert_name').value
                    print("UPDATING all: ",t, gaia)
                    gaia_alerts_harvester.update_gaia_lc(t, gaia)
                except:
                    print("target ",t,' not updated, probably no gaia_alert_name given.')  
            return 'Finished updating all light curves'
