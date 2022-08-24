from notes.models import Note
from rest_framework import serializers


class NoteSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Note
        fields = [
            'id',
            'created_at',
            'modified_at',
            'deleted_at',
            'title',
            'notes',
            'ticket_id',
            'job_id',
            'username',
            'account',
        ]
