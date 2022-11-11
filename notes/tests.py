from django.conf import settings
from tests.tests import CustomTestCase
from notes.models import Note


class NotesTestCase(CustomTestCase):
    def test_notes_anonymous(self):
        # A anonymous user should be redirected to login page
        response = self.client.get('/secure/notes/')
        self.assertEqual(response.status_code, 302)

    def test_notes_access(self):
        response = self.user_client.get('/secure/notes/')
        self.assertRedirects(response, '/admin/login/?next=/secure/notes/')

        response = self.admin_client.get('/secure/notes/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All notes')

    def test_notes_table_api(self):
        response = self.admin_client.get('/api/notes/?format=datatables')
        self.assertEqual(response.status_code, 200)
        self.assertJSONKeys(response, ['draw', 'recordsTotal', 'recordsFiltered', 'data'])

    def test_notes_add(self):
        response = self.admin_client.get('/secure/notes/new/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New note')

        response = self.admin_client.post('/secure/notes/new/', {
            'title': 'Test note',
            'notes': 'content',
            'username': settings.TESTS_USER,
            'send': 'new',
            'next': '/secure/notes/',
        })
        self.assertRedirects(response, '/secure/notes/')
        self.assertEqual(Note.objects.count(), 1)

        saved_note = Note.objects.get(title='Test note')
        response = self.admin_client.get('/secure/notes/{id}/'.format(id=saved_note.id))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test note')
        self.assertContains(response, 'content')

    def test_notes_update(self):
        note = Note.objects.create(
            title='Test note',
            notes='content',
            username=settings.TESTS_USER,
        )
        note.save()
        response = self.admin_client.get('/secure/notes/{id}/'.format(id=note.id))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Update note')

        response = self.admin_client.post('/secure/notes/{id}/'.format(id=note.id), {
            'title': 'Test note',
            'notes': 'content edited',
            'username': settings.TESTS_USER,
            'send': 'update',
            'next': '/secure/notes/',
        })
        self.assertRedirects(response, '/secure/notes/')
        self.assertEqual(Note.objects.count(), 1)

        saved_note = Note.objects.get(title='Test note')
        response = self.admin_client.get('/secure/notes/{id}/'.format(id=saved_note.id))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test note')
        self.assertContains(response, 'content edited')

    def test_notes_delete(self):
        note = Note.objects.create(
            title='Test note',
            notes='content',
            username=settings.TESTS_USER,
        )
        note.save()
        self.assertEqual(Note.objects.count(), 1)
        response = self.admin_client.post('/secure/notes/{id}/'.format(id=note.id), {
            'next': '/secure/notes/',
            'send': 'delete',
        })
        self.assertRedirects(response, '/secure/notes/')
        # We don't delete, but set a deleted_at field
        self.assertEqual(Note.objects.count(), 1)
        self.assertIsNotNone(Note.objects.get(title='Test note').deleted_at)
