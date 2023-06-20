from rest_framework import serializers
from effugium.models import RawLevelData

# class RawLevelDataSerializer(serializers.Serializer):
#     userId = serializers.CharField()
#     rawData = serializers.JSONField()
#     edata = serializers.JSONField()
#     parameters = serializers.JSONField()
#     completeAttempt = serializers.JSONField()
#     userIP = serializers.JSONField()
#     urlParameters = serializers.JSONField()
#     timeCreated = serializers.DateTimeField()
#     lastModified = serializers.DateTimeField()

class RawLevelDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawLevelData
        fields = '__all__'