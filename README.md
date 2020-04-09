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
$ python manage.py makemigrations myapp
$ python manage.py migrate
$ python manage.py createsuperuser
$ python manage.py collectstatic
```

```
$ python manage.py runserver

```

# Add filtr

Add filtrs to your local database from cpcs.

```
insert into myapp_catalogs values(1,'SDSS',ARRAY['u','g','r','i','z','B','V','R','I']);
insert into myapp_catalogs values(2,'USNO',ARRAY['B1pg','B2pg','R1pg','R2pg','Ipg']);
insert into myapp_catalogs values(3,'2MASS',ARRAY['J','H','K']);
insert into myapp_catalogs values(4,'APASS',ARRAY['B','V','g','r','i']);
insert into myapp_catalogs values(5,'OGLE3',ARRAY['V','I']);
insert into myapp_catalogs values(6,'PS1',ARRAY['g','r','i']);
insert into myapp_catalogs values (7,'VSTATLAS',ARRAY['u','g','r','i','z']);

```


# Upload files

Adres for send fits to bhtom:  /upload/

Sending parameters in 'data': hashtag, target(name),filter, data_product_type (photometry, fits_file, spectroscopy, image_file) 

Sending file in 'files'

Exemple: 
    post('url/upload/', data = {'hashtag': hashtag, 'target': target.name, 'filter': 'APASS/V', data_product_type':  fits_file}, files={'files': file})




