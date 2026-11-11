from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import Annotation, Document, Rendition, Snapshot


@override_settings(ALLOWED_HOSTS=["testserver"])
class RetiredAnnotationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user("owner")
        self.reviewer = users.objects.create_user("reviewer", is_staff=True)
        self.staff = users.objects.create_superuser("staff", "staff@example.test", "password")
        document = Document.objects.create(url="https://communistusa.org/example/")
        snapshot = Snapshot.objects.create(document=document, digest="a" * 64, manifest={})
        self.version = Rendition.objects.create(
            document=document,
            snapshot=snapshot,
            identity="b" * 64,
            title="Example",
            structure={"toc": []},
            html="<p>Retained article text.</p>",
            stylesheet="",
            app_version="test",
            adapter_version="1",
            format_version="1",
            output_digest="c" * 64,
        )
        self.book = Rendition.objects.create(
            document=document,
            snapshot=snapshot,
            identity="d" * 64,
            title="Example book",
            structure={"book": True, "toc": []},
            html="<p>Retained book text.</p>",
            stylesheet="",
            app_version="test",
            adapter_version="1",
            format_version="1",
            output_digest="e" * 64,
        )
        self.annotation = Annotation.objects.create(
            owner=self.owner,
            rendition=self.version,
            start=0,
            end=8,
            quote="PRIVATE_MARK_78F31",
            kind=Annotation.Kind.HIGHLIGHT,
            color=Annotation.Color.YELLOW,
        )
        self.collection_url = reverse("annotations", args=[self.version.pk])
        self.detail_url = reverse("annotation", args=[self.version.pk, self.annotation.pk])
        self.preserved_url = reverse("preserved-annotations")
        self.record_before = Annotation.objects.values().get(pk=self.annotation.pk)

    def test_api_routes_are_gone_for_every_role_and_method_without_mutation(self):
        clients = [Client(enforce_csrf_checks=True) for _ in range(4)]
        clients[1].force_login(self.owner)
        clients[2].force_login(self.reviewer)
        clients[3].force_login(self.staff)
        methods = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
        routes = (self.collection_url, self.detail_url)

        for client in clients:
            for url in routes:
                for method in methods:
                    with self.subTest(user=client, url=url, method=method):
                        response = client.generic(
                            method,
                            url,
                            data='{"kind":"underline","color":"blue"}',
                            content_type="application/json",
                        )
                        self.assertEqual(response.status_code, 410)
                        self.assertNotContains(response, self.annotation.quote, status_code=410)

        self.assertEqual(Annotation.objects.values().get(pk=self.annotation.pk), self.record_before)

    def test_pdf_output_does_not_expose_retained_private_quote(self):
        response = Client().get(reverse("reader-pdf", args=[self.version.pk]))
        self.assertEqual(response.status_code, 200)
        pdf = b"".join(response.streaming_content)
        self.assertNotIn(self.annotation.quote.encode(), pdf)
        self.assertEqual(Annotation.objects.values().get(pk=self.annotation.pk), self.record_before)

    def test_preserved_page_is_retired_for_all_roles(self):
        clients = [Client(enforce_csrf_checks=True) for _ in range(4)]
        clients[1].force_login(self.owner)
        clients[2].force_login(self.reviewer)
        clients[3].force_login(self.staff)

        for client in clients:
            for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
                with self.subTest(user=client, method=method):
                    response = client.generic(method, self.preserved_url)
                    self.assertEqual(response.status_code, 410)
                    self.assertNotContains(response, self.annotation.quote, status_code=410)

        self.assertEqual(Annotation.objects.values().get(pk=self.annotation.pk), self.record_before)

    def test_reader_has_no_annotation_ui_or_data_request_for_any_role(self):
        clients = [Client(), Client(), Client(), Client()]
        clients[1].force_login(self.owner)
        clients[2].force_login(self.reviewer)
        clients[3].force_login(self.staff)
        for rendition in (self.version, self.book):
            reader_url = reverse("reader", args=[rendition.pk])
            for client in clients:
                with self.subTest(user=client, rendition=rendition.pk):
                    response = client.get(reader_url)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(response, self.annotation.quote)
                    self.assertNotContains(response, "annotation")
                    self.assertNotContains(response, "highlight or underline")
                    self.assertNotContains(response, "annotations.js")
                    self.assertNotContains(response, self.collection_url)

        self.assertEqual(Annotation.objects.values().get(pk=self.annotation.pk), self.record_before)
