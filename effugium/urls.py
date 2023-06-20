from django.contrib import admin
from django.urls import path, include

import effugium.views as _v

urlpatterns = [
    path('begin/<str:userId>/', _v.effugiumView),
    path('endData/', _v.getExptDataView),
    path('riseEP/', _v.testRiseEndpoint),
    path('rise/', _v.effugiumView),
    path('rmBlacklisted/<str:IP>/', _v.removeBlacklistedIp),
    path("validateParticipant/", _v.validateRiseParticipant),
    path("dumpData/<str:type>/", _v.dumpData),
    path("completed/", _v.confirmComplete),
    path("getData/", _v.getQueryDataView),
    path("queryDB/", _v.queryDB),
]