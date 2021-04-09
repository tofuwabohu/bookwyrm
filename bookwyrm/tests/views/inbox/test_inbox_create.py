""" tests incoming activities"""
import json
import pathlib
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxActivities(TestCase):
    """ readthrough tests """

    def setUp(self):
        """ basic user and book data """
        self.local_user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
        )
        self.local_user.remote_id = "https://example.com/user/mouse"
        self.local_user.save(broadcast=False)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            with patch("bookwyrm.activitystreams.ActivityStream.add_status"):
                self.status = models.Status.objects.create(
                    user=self.local_user,
                    content="Test status",
                    remote_id="https://example.com/status/1",
                )
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )

        self.create_json = {
            "id": "hi",
            "type": "Create",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }
        models.SiteSettings.objects.create()

    def test_handle_create_status(self):
        """ the "it justs works" mode """
        self.assertEqual(models.Status.objects.count(), 1)

        datafile = pathlib.Path(__file__).parent.joinpath(
            "../../data/ap_quotation.json"
        )
        status_data = json.loads(datafile.read_bytes())
        models.Edition.objects.create(
            title="Test Book", remote_id="https://example.com/book/1"
        )
        activity = self.create_json
        activity["object"] = status_data

        with patch("bookwyrm.activitystreams.ActivityStream.add_status") as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)

        status = models.Quotation.objects.get()
        self.assertEqual(
            status.remote_id, "https://example.com/user/mouse/quotation/13"
        )
        self.assertEqual(status.quote, "quote body")
        self.assertEqual(status.content, "commentary")
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(models.Status.objects.count(), 2)

        # while we're here, lets ensure we avoid dupes
        views.inbox.activity_task(activity)
        self.assertEqual(models.Status.objects.count(), 2)

    def test_handle_create_status_remote_note_with_mention(self):
        """ should only create it under the right circumstances """
        self.assertEqual(models.Status.objects.count(), 1)
        self.assertFalse(
            models.Notification.objects.filter(user=self.local_user).exists()
        )

        datafile = pathlib.Path(__file__).parent.joinpath("../../data/ap_note.json")
        status_data = json.loads(datafile.read_bytes())
        activity = self.create_json
        activity["object"] = status_data

        with patch("bookwyrm.activitystreams.ActivityStream.add_status") as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        status = models.Status.objects.last()
        self.assertEqual(status.content, "test content in note")
        self.assertEqual(status.mention_users.first(), self.local_user)
        self.assertTrue(
            models.Notification.objects.filter(user=self.local_user).exists()
        )
        self.assertEqual(models.Notification.objects.get().notification_type, "MENTION")

    def test_handle_create_status_remote_note_with_reply(self):
        """ should only create it under the right circumstances """
        self.assertEqual(models.Status.objects.count(), 1)
        self.assertFalse(models.Notification.objects.filter(user=self.local_user))

        datafile = pathlib.Path(__file__).parent.joinpath("../../data/ap_note.json")
        status_data = json.loads(datafile.read_bytes())
        del status_data["tag"]
        status_data["inReplyTo"] = self.status.remote_id
        activity = self.create_json
        activity["object"] = status_data

        with patch("bookwyrm.activitystreams.ActivityStream.add_status") as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        status = models.Status.objects.last()
        self.assertEqual(status.content, "test content in note")
        self.assertEqual(status.reply_parent, self.status)
        self.assertTrue(models.Notification.objects.filter(user=self.local_user))
        self.assertEqual(models.Notification.objects.get().notification_type, "REPLY")

    def test_handle_create_list(self):
        """ a new list """
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/list/22",
            "type": "BookList",
            "totalItems": 1,
            "first": "https://example.com/list/22?page=1",
            "last": "https://example.com/list/22?page=1",
            "name": "Test List",
            "owner": "https://example.com/user/mouse",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "summary": "summary text",
            "curation": "curated",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        book_list = models.List.objects.get()
        self.assertEqual(book_list.name, "Test List")
        self.assertEqual(book_list.curation, "curated")
        self.assertEqual(book_list.description, "summary text")
        self.assertEqual(book_list.remote_id, "https://example.com/list/22")
