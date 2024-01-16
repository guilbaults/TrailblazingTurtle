from jobstats.models import JobScript
from slurm.models import JobTable
from rest_framework import serializers
import time
import datetime


class JobScriptSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = JobScript
        fields = ['id_job', 'submit_script']


class UnixEpochDateField(serializers.DateTimeField):
    def to_internal_value(self, value):
        """ Return epoch time for a datetime object or ``None``"""
        try:
            return int(time.mktime(value.timetuple()))
        except (AttributeError, TypeError):
            return None

    def to_representation(self, value):
        if value == 0:
            return None
        return datetime.datetime.fromtimestamp(int(value), tz=datetime.timezone.utc)


class JobSerializer(serializers.HyperlinkedModelSerializer):
    time_submit = UnixEpochDateField()
    time_start = UnixEpochDateField()
    time_eligible = UnixEpochDateField()
    time_end = UnixEpochDateField()

    class Meta:
        model = JobTable
        fields = [
            'id_job',
            'job_name',
            'account',
            'time_submit',
            'time_start',
            'time_eligible',
            'time_end',
            'timelimit',
            'get_state_display',
            'nodes',
            'username']
