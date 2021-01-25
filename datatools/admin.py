from django.contrib import admin
from bhtom.models import BHTomFits, Instrument, Observatory, BHTomUser
from django.http import FileResponse
import os

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
    list_display = ('obsName','prefix', 'cpcsOnly', 'obsInfo', 'isVerified', 'comment')

class BHTomUser_displayField(admin.ModelAdmin):
    list_display = ('get_user', 'get_firstName', 'get_lastName', 'get_email', 'latex_name','latex_affiliation',
                    'address', 'about_me', 'get_isLogin', 'is_activate')

    def get_user(self, obj):
        return obj.user.username
    get_user.short_description = 'User name'

    def get_firstName(self, obj):
        return obj.user.first_name
    get_firstName.short_description = 'First name'

    def get_lastName(self, obj):
        return obj.user.last_name
    get_lastName.short_description = 'Last name'

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

    def get_isLogin(self, obj):
        return obj.user.is_active
    get_isLogin.boolean = True
    get_isLogin.short_description = 'Can login'

admin.site.register(BHTomFits, BHTomFits_displayField)
admin.site.register(Instrument, Instrument_displayField)
admin.site.register(Observatory, Observatory_displayField)
admin.site.register(BHTomUser, BHTomUser_displayField)