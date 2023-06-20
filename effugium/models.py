from django.db import models

# Create your models here.

class RawLevelData(models.Model):

    userId = models.CharField(max_length = 128, unique=True)
    rawData = models.JSONField(blank=True, null=True)
    edata = models.JSONField(blank=True, null=True)
    parameters = models.JSONField(blank=True, null=True)
    completeAttempt = models.JSONField(blank=True, null=True)
    userIP = models.CharField(max_length=64, blank=True)
    urlParameters = models.JSONField(blank=True, null=True)
    timeCreated = models.DateTimeField(auto_now_add=True)
    lastModified = models.DateTimeField(auto_now=True)