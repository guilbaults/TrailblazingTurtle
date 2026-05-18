from maas.models import MAASUsageRecord
from rest_framework import serializers


class MAASUsageSubmitSerializer(serializers.Serializer):
    provider_key = serializers.CharField(required=True, write_only=True)
    model = serializers.CharField(max_length=255, required=True)
    endpoint = serializers.CharField(max_length=500, required=True)
    input_tokens = serializers.IntegerField(min_value=0, required=True)
    output_tokens = serializers.IntegerField(min_value=0, required=True)
    cost = serializers.DecimalField(max_digits=10, decimal_places=6, required=False, allow_null=True)
    latency_ms = serializers.IntegerField(min_value=0, required=True)
    request_id = serializers.CharField(max_length=255, required=False)


class MAASUsageRecordSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.ReadOnlyField(source='api_key.user.username')
    provider_name = serializers.ReadOnlyField(source='provider.name')

    class Meta:
        model = MAASUsageRecord
        fields = [
            'id',
            'user',
            'provider_name',
            'request_id',
            'model',
            'endpoint',
            'input_tokens',
            'output_tokens',
            'cost',
            'latency_ms',
            'created_at',
        ]


class MAASVerifyRequestSerializer(serializers.Serializer):
    provider_key = serializers.CharField(required=True, write_only=True)
