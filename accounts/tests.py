from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ContactMessage, CustomUser


class ContactMessageAPITests(APITestCase):
    def setUp(self):
        self.list_url = reverse('contact_messages-list')
        self.payload = {
            'name': 'Test Customer',
            'email': 'customer@example.com',
            'phone_number': '+919876543210',
            'subject': 'feedback',
            'message': 'The contact form is working well.',
        }

    def test_public_user_can_create_contact_message(self):
        response = self.client.post(self.list_url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = ContactMessage.objects.get()
        self.assertEqual(message.email, self.payload['email'])
        self.assertFalse(message.is_read)

    def test_public_user_cannot_mark_new_message_as_read(self):
        payload = {**self.payload, 'is_read': True}

        response = self.client.post(self.list_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(ContactMessage.objects.get().is_read)

    def test_public_user_cannot_list_contact_messages(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_list_and_mark_contact_message_as_read(self):
        admin_user = CustomUser.objects.create_user(
            username='contact_admin',
            phone_number='+919999999999',
            password='TestPassword123!',
            role='admin',
        )
        message = ContactMessage.objects.create(**self.payload)
        self.client.force_authenticate(user=admin_user)

        list_response = self.client.get(self.list_url)
        detail_url = reverse('contact_messages-detail', kwargs={'pk': message.pk})
        patch_response = self.client.patch(detail_url, {'is_read': True}, format='json')

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        message.refresh_from_db()
        self.assertTrue(message.is_read)
