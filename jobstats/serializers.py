from jobstats.models import JobScript
from rest_framework import serializers


class JobScriptSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = JobScript
        fields = ['id_job', 'submit_script']
