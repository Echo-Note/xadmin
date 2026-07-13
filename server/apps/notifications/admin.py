"""通知应用的 Django Admin 注册。"""

from django.contrib import admin

from apps.notifications.models import *

admin.site.register(MessageContent)
admin.site.register(MessageUserRead)
admin.site.register(UserMsgSubscription)
admin.site.register(SystemMsgSubscription)
