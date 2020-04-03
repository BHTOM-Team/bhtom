from django.contrib import admin
from myapp.models import BHTomFits, Cpcs_user


class BhtonFitsField(admin.ModelAdmin):
    list_display = ('fits_id','status', )

class Cpcs_displayField(admin.ModelAdmin):
    list_display = ('user','obsName')

admin.site.register(BHTomFits, BhtonFitsField)
admin.site.register(Cpcs_user, Cpcs_displayField)
