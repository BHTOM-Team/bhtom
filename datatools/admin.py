from django.contrib import admin
from bhtom.models import BHTomFits, Instrument, Observatory


class BHTomFits_displayField(admin.ModelAdmin):
    list_display = ('file_id', 'get_instrument', 'get_meesage', 'get_dataProduct')

    def get_instrument(self, obj):
        return obj.instrument_id

    get_instrument.short_description = 'User name'

    def get_meesage(self, obj):
        return obj.status_message

    get_meesage.short_description = 'Description'


    def get_dataProduct(self, obj):
        return obj.dataproduct_id.data_product_type

    get_dataProduct.short_description = 'Product type'

class Instrument_displayField(admin.ModelAdmin):
    list_display = ('user_id','get_obsName', 'isActive', 'comment')

    def get_obsName(self, obj):
        return obj.observatory_id.obsName

    get_obsName.short_description = 'observatory name'


class Observatory_displayField(admin.ModelAdmin):
    list_display = ('obsName','prefix', 'cpcsOnly', 'isVerified', 'comment')

admin.site.register(BHTomFits, BHTomFits_displayField)
admin.site.register(Instrument, Instrument_displayField)
admin.site.register(Observatory, Observatory_displayField)
