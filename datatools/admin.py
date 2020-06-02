from django.contrib import admin
from bhtom.models import BHTomFits, Instrument, Observatory


class BHTomFits_displayField(admin.ModelAdmin):
    list_display = ('file_id','status', )

class Instrument_displayField(admin.ModelAdmin):
    list_display = ('user_id','observatory_id')

class Observatory_displayField(admin.ModelAdmin):
    list_display = ('obsName','prefix')

admin.site.register(BHTomFits, BHTomFits_displayField)
admin.site.register(Instrument, Instrument_displayField)
admin.site.register(Observatory, Observatory_displayField)
