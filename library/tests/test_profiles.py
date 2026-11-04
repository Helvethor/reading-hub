from dataclasses import replace
from types import ModuleType
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from library.profile import SourceSite, get_profile
from library.services.errors import ImportFailure
from library.services.fetch import canonical_url, validate_url
from library.sources.adapters import discover, extract
from library.sources.base import Part, Source, parse_html
from library.tests import test_pipeline
from library.tests.test_sources import ARTICLE, article_html
from profiles.marxist.site import PROFILE


class ExampleAdapter:
    @staticmethod
    def discover(soup, url):
        return Source("Science article", {"language": "en"}, [Part(url, "Science article")], False)

    @staticmethod
    def extract(soup, url, **options):
        return soup.find("article")


EXAMPLE = replace(
    PROFILE,
    key="science",
    name="Science Library",
    tagline="A different subject",
    headline="Science without distractions.",
    introduction="Independent science reading.",
    footer="A reusable reader.",
    theme_css="neutral/theme.css",
    admin_theme_css="",
    sources=(
        SourceSite("example.org", "Example Science", "library.tests.test_profiles.ExampleAdapter"),
    ),
    aliases={"www.example.org": "example.org"},
    asset_paths={"images.example.org": ("/figures/",)},
    catalogue_redirects={},
    sort_choices=("title", "oldest"),
    default_sort="title",
    source_filter=False,
    page_size=1,
    catalogue_enabled=False,
)


class ProfileTests(SimpleTestCase):
    def test_default_profile_is_valid(self):
        profile = get_profile().validate()
        self.assertEqual(profile.key, "marxist")
        self.assertEqual(
            next(source.label for source in profile.sources if source.host == "communisme.ch"),
            "PCR · Suisse",
        )

    def test_alternate_profile_dispatches_without_engine_changes(self):
        with (
            patch("library.profile.get_profile", return_value=EXAMPLE),
            patch("library.services.fetch.get_profile", return_value=EXAMPLE),
            patch("library.sources.adapters.get_profile", return_value=EXAMPLE),
        ):
            self.assertEqual(EXAMPLE.validate(), EXAMPLE)
            url = canonical_url("http://www.example.org/paper/")
            self.assertEqual(url, "https://example.org/paper/")
            soup = parse_html(b"<article>Science test content.</article>")
            self.assertEqual(discover(soup, url).title, "Science article")
            self.assertEqual(extract(soup, url).get_text(), "Science test content.")
            self.assertEqual(
                validate_url("https://images.example.org/figures/a.png", asset=True),
                "https://images.example.org/figures/a.png",
            )
            for url in [ARTICLE, "https://images.example.org/other/a.png"]:
                with self.assertRaises(ImportFailure):
                    validate_url(url, asset=True)
            with self.assertRaises(ImportFailure):
                discover(soup, ARTICLE)

    def test_bad_configuration_fails_explicitly(self):
        cases = [
            {"page_size": 0},
            {"request_timeout": -1},
            {"request_interval": 0},
            {"max_pages": True},
            {"max_bytes": 0},
            {"default_sort": "sql"},
            {"sort_choices": ("sql",)},
            {"aliases": {"bad.example": "unknown.example"}},
            {"sources": ()},
            {"asset_paths": {"cdn.example": ("relative/",)}},
            {"theme_css": "../bad.css"},
            {"theme_css": "absent.css"},
            {"admin_theme_css": "../bad.css"},
            {"admin_theme_css": "absent.css"},
            {"source_filter": "yes"},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ImproperlyConfigured):
                replace(PROFILE, **values).validate()

    def test_environment_selects_profile(self):
        module = ModuleType("custom_site_profile")
        module.PROFILE = EXAMPLE
        with (
            patch.dict("sys.modules", {"custom_site_profile": module}),
            override_settings(READING_HUB_PROFILE="custom_site_profile"),
        ):
            self.assertEqual(get_profile().key, "science")


class ProfileLibraryTests(TestCase):
    setUp = test_pipeline.PipelineTests.setUp
    fetch = test_pipeline.PipelineTests.fetch
    import_article = test_pipeline.PipelineTests.import_article

    def test_profile_stylesheet_loads_after_page_styles_for_editor_overrides(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        result = self.import_article()
        reviewer = get_user_model().objects.create_user("theme-reviewer", is_staff=True)
        self.client.force_login(reviewer)
        with override_settings(READING_HUB_EDITOR_PILOT=True):
            response = self.client.get(reverse("document-editor", args=[result.pk]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertLess(html.index("library/editor-pilot.css"), html.index("marxist/theme.css"))
        self.assertContains(response, "editor-outline-items")
        self.assertContains(response, "editor-section-move")
        self.assertContains(response, "editor-contributors")

    def test_sort_filter_and_pagination(self):
        self.content = article_html(title="Zulu")
        first = self.import_article()
        from library.services.pipeline import claim_job, enqueue, process_job

        self.content = article_html(title="Alpha")
        enqueue("https://communistusa.org/second/")
        second = process_job(claim_job())
        response = self.client.get("/?sort=title")
        self.assertEqual(
            [d.pk for d in response.context["documents"]], [second.document_id, first.document_id]
        )
        self.assertEqual(
            [d.pk for d in self.client.get("/?sort=oldest").context["documents"]],
            [first.document_id, second.document_id],
        )
        self.assertEqual(
            [d.pk for d in self.client.get("/?sort=newest").context["documents"]],
            [second.document_id, first.document_id],
        )
        response = self.client.get("/?source=marxist.com")
        self.assertEqual(len(response.context["documents"]), 0)
        response = self.client.get("/?source=communistusa.org")
        self.assertEqual(response.context["page"].paginator.count, 2)
        with patch("library.views.get_profile", return_value=replace(PROFILE, page_size=1)):
            response = self.client.get("/?sort=title&source=communistusa.org&page=2")
            self.assertEqual(response.context["page"].number, 2)
            self.assertContains(response, "sort=title&amp;source=communistusa.org")
            self.assertEqual(response.context["documents"][0].pk, first.document_id)

    def test_unrecognized_controls_report_errors(self):
        response = self.client.get("/?sort=bad&source=bad.example")
        self.assertContains(response, "Unknown sort option")
        self.assertContains(response, "Unknown source filter")

    def test_alternate_profile_controls_branding_and_controls(self):
        with (
            patch("library.profile.get_profile", return_value=EXAMPLE),
            patch("library.views.get_profile", return_value=EXAMPLE),
        ):
            response = self.client.get("/")
        self.assertContains(response, "Science Library")
        self.assertContains(response, "Science without distractions.")
        self.assertContains(response, "neutral/theme.css")
        self.assertContains(response, "example.org")
        self.assertNotContains(response, "communistusa.org")
        self.assertNotContains(response, 'id="source"')
        self.assertNotContains(response, 'value="newest"')

    def test_theme_assets_resolve_locally(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find("marxist/theme.css"))
        self.assertIsNotNone(finders.find("marxist/lenin-red.png"))
        self.assertContains(self.client.get("/"), "/static/marxist/theme.css")
