from django.contrib import admin

# Register your models here.

from myapp.models import BHTomFits, Cpcs_user

admin.site.register(BHTomFits)
admin.site.register(Cpcs_user)

