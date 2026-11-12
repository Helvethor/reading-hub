import json
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from library.models import (
    ReadingStyleAccountDefault,
    ReadingStyleAdminDefault,
    ReadingStyleOutputOverride,
    ReadingStyleProfile,
    Rendition,
    Snapshot,
)
from library.services.reading_styles import (
    DEFAULTS,
    resolve_style,
    style_presentation_token,
    token_presentation,
)


class ReadingStyleCascadeTests(TestCase):
    def setUp(self):
        from library.tests.test_printing import PrintingTests

        PrintingTests.setUp(self)
        self.version.metadata["work_type"] = "article"
        self.version.save(update_fields=["metadata"])
        self.owner = get_user_model().objects.create_user("style-owner", password="secret")
        self.other = get_user_model().objects.create_user("style-other", password="secret")
        self.update_url = reverse("reading-style-preview")

    def post_style(self, client, **payload):
        return client.post(
            self.update_url, data=json.dumps(payload), content_type="application/json",
        )

    def copy_version(self, identity):
        snapshot = Snapshot.objects.create(
            document=self.version.document, digest=identity, manifest={},
        )
        return Rendition.objects.create(
            document=self.version.document,
            snapshot=snapshot,
            identity=identity,
            title=self.version.title,
            metadata=self.version.metadata,
            structure=self.version.structure,
            html=self.version.html,
            stylesheet=self.version.stylesheet,
            app_version=self.version.app_version,
            adapter_version=self.version.adapter_version,
            format_version=self.version.format_version,
            output_digest=identity,
        )

    def test_sparse_cascade_tracks_origins_and_resets_false_zero_and_missing(self):
        ReadingStyleAdminDefault.objects.create(
            work_type="article",
            settings={
                "font_size": 16, "italic_to_bold": True, "letter_spacing": .04,
                "hyphenation": True, "paragraph_spacing": .75,
            },
        )
        ReadingStyleAccountDefault.objects.create(
            owner=self.owner, work_type="article",
            settings={"font_size": 18, "italic_to_bold": False, "word_spacing": 0},
        )
        ReadingStyleOutputOverride.objects.create(
            owner=self.owner, rendition=self.version,
            settings={
                "font_size": 20, "italic_to_bold": True, "letter_spacing": 0,
                "hyphenation": False,
            },
        )
        resolved = resolve_style("article", user=self.owner, rendition=self.version)
        self.assertEqual(resolved["settings"]["font_size"], 20)
        self.assertEqual(resolved["origins"]["font_size"]["source"], "output")
        self.assertTrue(resolved["settings"]["italic_to_bold"])
        self.assertEqual(resolved["origins"]["italic_to_bold"]["source"], "output")
        self.assertEqual(resolved["settings"]["letter_spacing"], 0)
        self.assertEqual(resolved["origins"]["letter_spacing"]["source"], "output")
        self.assertEqual(resolved["settings"]["word_spacing"], 0)
        self.assertEqual(resolved["origins"]["word_spacing"]["source"], "account")
        self.assertFalse(resolved["settings"]["hyphenation"])
        self.assertEqual(resolved["origins"]["hyphenation"]["source"], "output")
        self.assertEqual(resolved["settings"]["paragraph_spacing"], .75)
        self.assertEqual(resolved["origins"]["paragraph_spacing"]["source"], "administrator")

        self.client.force_login(self.owner)
        reset = self.post_style(
            self.client,
            scope="output",
            rendition_id=self.version.pk,
            work_type="article",
            reset=["font_size", "italic_to_bold", "letter_spacing", "hyphenation"],
        )
        self.assertEqual(reset.status_code, 200, reset.content)
        result = reset.json()
        self.assertEqual(result["settings"]["font_size"], 18)
        self.assertEqual(result["origins"]["font_size"]["source"], "account")
        self.assertFalse(result["settings"]["italic_to_bold"])
        self.assertEqual(result["origins"]["italic_to_bold"]["source"], "account")
        self.assertEqual(result["settings"]["letter_spacing"], .04)
        self.assertEqual(result["origins"]["letter_spacing"]["source"], "administrator")
        self.assertTrue(result["settings"]["hyphenation"])
        self.assertEqual(result["origins"]["hyphenation"]["source"], "administrator")
        self.assertFalse(
            ReadingStyleOutputOverride.objects.filter(
                owner=self.owner, rendition=self.version,
            ).exists(),
            "Resetting every explicit field removes the sparse exact-output layer.",
        )

        ReadingStyleAdminDefault.objects.filter(work_type="article").update(
            settings={"paragraph_spacing": 1.25},
        )
        changed_lower_layer = resolve_style("article", user=self.owner, rendition=self.version)
        self.assertEqual(changed_lower_layer["settings"]["paragraph_spacing"], 1.25)
        self.assertEqual(
            changed_lower_layer["origins"]["paragraph_spacing"]["source"], "administrator",
        )

    def test_type_defaults_fall_back_to_other_without_inferring_from_structure(self):
        self.version.structure["book"] = True
        self.version.metadata.pop("work_type", None)
        self.version.save(update_fields=["metadata", "structure"])
        ReadingStyleAdminDefault.objects.create(
            work_type="book", settings={"font_size": 22},
        )
        result = resolve_style("unknown-type", user=self.owner, rendition=self.version)
        self.assertEqual(result["work_type"], "other")
        self.assertEqual(result["settings"]["font_size"], DEFAULTS["font_size"])
        self.assertEqual(result["origins"]["font_size"]["label"], "Built-in · Other")

    def test_account_and_exact_output_preferences_are_private_and_not_propagated(self):
        ReadingStyleAccountDefault.objects.create(
            owner=self.owner, work_type="article", settings={"font_size": 18},
        )
        ReadingStyleOutputOverride.objects.create(
            owner=self.owner, rendition=self.version, settings={"font_size": 22},
        )
        successor = self.copy_version("d" * 64)
        self.assertEqual(
            resolve_style("article", user=self.owner, rendition=self.version)["settings"]["font_size"],
            22,
        )
        successor_style = resolve_style("article", user=self.owner, rendition=successor)
        self.assertEqual(successor_style["settings"]["font_size"], 18)
        self.assertEqual(successor_style["origins"]["font_size"]["source"], "account")

        self.client.force_login(self.other)
        other_style = resolve_style("article", user=self.other, rendition=self.version)
        self.assertEqual(other_style["settings"]["font_size"], DEFAULTS["font_size"])
        self.assertEqual(ReadingStyleOutputOverride.objects.count(), 1)

    def test_guest_output_override_is_ephemeral_until_explicit_login_import(self):
        guest = Client()
        guest.cookies["reading_hub_theme"] = "dark"
        preview = self.post_style(
            guest,
            scope="output",
            rendition_id=self.version.pk,
            work_type="article",
            changes={"italic_to_bold": True, "letter_spacing": 0, "palette": "theme"},
            guest_overrides={},
        )
        self.assertEqual(preview.status_code, 200, preview.content)
        result = preview.json()
        self.assertFalse(result["persisted"])
        self.assertEqual(result["layer"], {
            "italic_to_bold": True, "letter_spacing": 0.0, "palette": "theme",
        })
        self.assertFalse(ReadingStyleOutputOverride.objects.exists())
        self.assertTrue(token_presentation(result["presentation"])["settings"]["italic_to_bold"])
        self.assertEqual(token_presentation(result["presentation"])["theme"], "dark")
        self.assertEqual(parse_qs(urlsplit(result["stylesheet"]).query), {
            "style": [result["token"]], "theme": ["dark"], "v": ["7"],
        })
        self.assertIn(
            "background: transparent",
            guest.get(result["stylesheet"]).content.decode(),
        )

        class MemoryPdf:
            def open(self, _mode):
                return BytesIO(b"%PDF appearance snapshot")

        pdf_url = reverse("reader-pdf", args=[self.version.pk])
        with patch("library.views.cached_pdf", return_value=MemoryPdf()) as export:
            pdf = guest.get(pdf_url, {"presentation": result["presentation"]})
            self.assertEqual(pdf.status_code, 200)
            export.assert_called_once()
            self.assertEqual(export.call_args.args[1], result["settings"])
            self.assertEqual(export.call_args.kwargs["theme"], "dark")
            pdf.close()

        self.client.force_login(self.owner)
        imported = self.post_style(
            self.client,
            scope="output",
            rendition_id=self.version.pk,
            work_type="article",
            guest_overrides=result["layer"],
        )
        self.assertEqual(imported.status_code, 200, imported.content)
        self.assertFalse(
            ReadingStyleOutputOverride.objects.filter(owner=self.owner).exists(),
            "Loading a guest snapshot while logged in must not import it implicitly.",
        )
        bad_import = self.client.post(
            reverse("reading-style-import-guest"),
            data=json.dumps({
                "rendition_id": self.version.pk,
                "settings": {"unknown": "value"},
            }),
            content_type="application/json",
        )
        self.assertEqual(bad_import.status_code, 400)
        good_import = self.client.post(
            reverse("reading-style-import-guest"),
            data=json.dumps({"rendition_id": self.version.pk, "settings": result["layer"]}),
            content_type="application/json",
        )
        self.assertEqual(good_import.status_code, 200, good_import.content)
        exact = ReadingStyleOutputOverride.objects.get(owner=self.owner, rendition=self.version)
        self.assertEqual(exact.settings, result["layer"])

    def test_legacy_profile_requires_explicit_type_scoped_import_and_is_not_rewritten(self):
        legacy = {
            key: value for key, value in DEFAULTS.items() if key not in {"palette", "mode"}
        }
        legacy["contrast"] = "cream"
        profile = ReadingStyleProfile.objects.create(
            owner=self.owner, name="Legacy cream", settings=legacy, is_default=True,
        )
        self.client.force_login(self.owner)
        before = self.client.get(reverse("reader", args=[self.version.pk]))
        self.assertEqual(before.context["reading_style"], DEFAULTS)
        imported = self.client.post(
            reverse("reading-style-import-profile"),
            data=json.dumps({"profile_id": profile.pk, "work_type": "article"}),
            content_type="application/json",
        )
        self.assertEqual(imported.status_code, 200, imported.content)
        after = self.client.get(reverse("reader", args=[self.version.pk]))
        self.assertEqual(after.context["reading_style"]["palette"], "sepia")
        profile.refresh_from_db()
        self.assertEqual(profile.settings, legacy)
        self.assertTrue(profile.is_default)
        self.assertEqual(
            ReadingStyleAccountDefault.objects.get(owner=self.owner, work_type="article")
            .settings["palette"],
            "sepia",
        )
