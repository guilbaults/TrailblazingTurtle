from django.shortcuts import render, redirect
from django.http import HttpResponseNotFound
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from notes.models import Note
from rest_framework import viewsets
from rest_framework import permissions
from notes.serializers import NoteSerializer
import datetime


@login_required
@staff_member_required
def index(request):
    context = {}
    context['notes'] = Note.objects.all().order_by('-created_at').filter(deleted_at=None)
    return render(request, 'notes/index.html', context)


def redirect_success(request):
    next = request.POST.get('next', '/')
    return redirect(next)


@login_required
@staff_member_required
def note(request, note_id=None):
    context = {}
    try:
        if request.method == 'GET':
            context['note'] = Note.objects.get(id=note_id)
            context['referer'] = request.META.get('HTTP_REFERER')
            return render(request, 'notes/note.html', context)

        elif request.method == 'POST':
            if request.POST['send'] == 'delete':
                context['note'] = Note.objects.get(id=note_id)
                context['note'].deleted_at = datetime.datetime.now()
                context['note'].save()
                return redirect_success(request)

            if request.POST['job_id'] == '':
                job_id = None
            else:
                job_id = int(request.POST['job_id'])
            if request.POST['ticket_id'] == '':
                ticket_id = None
            else:
                ticket_id = request.POST['ticket_id']
            if request.POST['account'] == '':
                account = None
            else:
                account = request.POST['account']
            if request.POST['username'] == '':
                username = None
            else:
                username = request.POST['username']

            if request.POST['send'] == 'update':
                # Update the note
                old_note = Note.objects.get(id=note_id)
                context['note'] = Note.objects.get(id=note_id)
                context['note'].title = request.POST['title']
                context['note'].notes = request.POST['notes']
                context['note'].ticket_id = ticket_id
                context['note'].account = account
                context['note'].job_id = job_id
                context['note'].username = username
                try:
                    context['note'].full_clean()
                    context['note'].save()
                except ValidationError as err:
                    # Do something when validation is not passing
                    context['errors'] = err.messages
                    context['note'] = old_note
                    return render(request, 'notes/note.html', context)
                return redirect_success(request)
            else:
                # New note
                note = Note.objects.create(
                    title=request.POST['title'],
                    notes=request.POST['notes'],
                    ticket_id=ticket_id,
                    username=request.POST['username'],
                    account=account,
                    job_id=job_id,
                    created_by=request.user
                )
                note.save()
                return redirect_success(request)

    except Note.DoesNotExist:
        return HttpResponseNotFound(_('Note not found'))


@login_required
@staff_member_required
def new(request):
    context = {}
    if request.method == 'GET':
        context['referer'] = request.META.get('HTTP_REFERER')
        context['note'] = {}
        if 'username' in request.GET:
            context['note']['username'] = request.GET['username']
        if 'account' in request.GET:
            context['note']['account'] = request.GET['account']
        if 'job_id' in request.GET:
            context['note']['job_id'] = request.GET['job_id']
        return render(request, 'notes/note.html', context)
    if request.method == 'POST':
        return note(request, None)


class NoteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Note.objects.all().order_by('-created_at').filter(deleted_at=None)
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAdminUser]
