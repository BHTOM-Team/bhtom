from django.contrib import admin
from tom_dataproducts.models import ReducedDatum

from bhtom.models import BHTomFits, Instrument, Observatory, BHTomUser, BHTomCpcsTaskAsynch
from django.utils.html import format_html

from bhtom.utils.asynch.taskCPCS import add_task_to_cpcs_queue


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
    list_display = ('user_id', 'get_obsName', 'isActive', 'comment')

    def get_obsName(self, obj):
        return obj.observatory_id.obsName

    get_obsName.short_description = 'observatory name'


class Observatory_displayField(admin.ModelAdmin):
    list_display = ('obsName', 'prefix', 'cpcsOnly', 'get_obsInfo', 'get_fits', 'isVerified', 'comment')

    def get_obsInfo(self, obj):
        if obj.obsInfo:
            return format_html("<a href='/datatools/download/obsInfo/%s'>" % obj.id + str(obj.id) + "</a>")

    get_obsInfo.short_description = 'ObsInfo'
    get_obsInfo.allow_tags = True

    def get_fits(self, obj):
        if obj.fits:
            fits_filename: str = str(obj.fits).split('/')[-1]
            return format_html("<a href='/datatools/download/obsFits/%s'>" % obj.id + fits_filename + "</a>")

    get_fits.short_description = 'Sample fits'
    get_fits.allow_tags = True


class BHTomUser_displayField(admin.ModelAdmin):
    list_display = ('get_user', 'get_firstName', 'get_lastName', 'get_email', 'latex_name', 'latex_affiliation',
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


class ReducedDatum_display(admin.ModelAdmin):
    list_display = ('target', 'data_product', 'data_type', 'source_name', 'source_location', 'timestamp', 'value')
    list_filter = ('target', 'data_type', 'source_name')


class BHTomCpcsTaskAsynch_displayField(admin.ModelAdmin):
    list_display = ('id', 'get_url', 'get_status', 'target', 'data_send', 'data_created', 'number_tries')

    def get_url(self, obj):
        return obj.url

    get_url.short_description = 'file'

    def get_status(self, obj):
        return obj.get_status_display()

    get_status.short_description = 'status'

    def send_to_cpcs(self, request, queryset):
        queryset.update(status='TODO')
        for obj in queryset:
            add_task_to_cpcs_queue(str(obj.id))

    actions = [send_to_cpcs]


admin.site.register(BHTomFits, BHTomFits_displayField)
admin.site.register(Instrument, Instrument_displayField)
admin.site.register(Observatory, Observatory_displayField)
admin.site.register(BHTomUser, BHTomUser_displayField)
admin.site.register(ReducedDatum, ReducedDatum_display)
admin.site.register(BHTomCpcsTaskAsynch, BHTomCpcsTaskAsynch_displayField)
