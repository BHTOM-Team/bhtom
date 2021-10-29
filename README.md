BHtom
===========================
Welcome to Black Hole TOM, built using the TOM Toolkit.

## Instalation


* get project, create virtual python3 environment, and install requirements.txt
* create local database in postgres
```
CREATE DATABASE my_db ;
CREATE USER my_user PASSWORD '**********'
GRANT ALL PRIVILEGES ON DATABASE my_db to my_user;
```
* create `local_settings.py`
* run django migrations and create super user:

```
$ python manage.py makemigrations
$ python manage.py makemigrations bhtom
$ python manage.py migrate
$ python manage.py createsuperuser
$ python manage.py collectstatic
```

```
$ python manage.py runserver
```

# Local settings

You have to provide at least the following values:

```
SECRET_KEY = '...'
black_tom_DB_NAME = '...'
black_tom_DB_USER = '...'
black_tom_DB_PASSWORD = '...'
```

# Add filters

Add filtrs to your local database from cpcs.
e
```
insert into bhtom_catalogs values(1,'SDSS',ARRAY['u','g','r','i','z','B','V','R','I']);
insert into bhtom_catalogs values(2,'USNO',ARRAY['B1pg','B2pg','R1pg','R2pg','Ipg']);
insert into bhtom_catalogs values(3,'2MASS',ARRAY['J','H','K']);
insert into bhtom_catalogs values(4,'APASS',ARRAY['B','V','g','r','i']);
insert into bhtom_catalogs values(5,'OGLE3',ARRAY['V','I']);
insert into bhtom_catalogs values(6,'PS1',ARRAY['g','r','i']);
insert into bhtom_catalogs values (7,'VSTATLAS',ARRAY['u','g','r','i','z']);
insert into bhtom_catalogs values(8,'DECAPS', ARRAY['g', 'r', 'i', 'z']);

```


# Upload files

Address for sending fits files to bhtom:  /upload/

Sending parameters in 'data': hashtag, target(name),filter, data_product_type (photometry, fits_file, spectroscopy, image_file), MJD, ExpTime

Sending file in 'files'

Example: 
    post('url/upload/', data = {'hashtag': hashtag, 'target': target.name, 'filter': 'APASS/V', data_product_type':  fits_file}, files={'files': file})




