import os
import requests

# The directory containing all the necessary fits files
directory = '### DIRECTORY NAME ###'
target = '### TARGET NAME ###'
hashtag = '### YOUR HASHTAG ###'

filter = '### FILTER NAME ###'

data_product_type = 'fits_file'

# Dry run option should be set to "True" or "False" (as a string)
dry_run = '### DRY RUN ###'

for filename in os.listdir(directory):
    with open(os.path.join(directory, filename), 'rb') as f:
        print("Sending...")
        response = requests.post(
            url='https://dev.bh-tom.astrolabs.pl/photometry-upload/',
            headers={
                'hashtag': hashtag
            },
            data={
                'target': target,
                'filter': filter,
                'data_product_type': data_product_type,
                'dry_run': dry_run
            },
            files={'files': f}
        )
        print(response.status_code)
        print(response.text)
