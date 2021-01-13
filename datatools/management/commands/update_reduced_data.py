from django.core.management.base import BaseCommand
from tom_targets.models import Target

from .utils.result_messages import MessageStatus, encode_message


class UpdateReducedDataCommand(BaseCommand):

    source_name = ''

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
                return self.update_function(target, user_id)
            except Exception as e:
                return encode_message(MessageStatus.ERROR,
                                      f'There was a problem while updating {self.source_name} data for {target.name}: {e}')
        else:
            for target in Target.objects.all():
                try:
                    print(self.update_function(target, user_id))
                except Exception as e:
                    print(f'Problem with updating {self.source_name} data for the target {target.pk}: {e}')
            return encode_message(MessageStatus.SUCCESS,
                                  f'Updated {self.source_name} data for all targets')

    def update_function(self, target, user_id) -> str:
        return ""
