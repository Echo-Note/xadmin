from django.contrib import admin

# Register your models here.
from apps.notifications.models import *

admin.site.register(MessageContent)
admin.site.register(MessageUserRead)
admin.site.register(UserMsgSubscription)
admin.site.register(SystemMsgSubscription)
