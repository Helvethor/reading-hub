import json
import os
import subprocess
import sys
import tempfile

from django.conf import settings
from django.test import SimpleTestCase


class ProcessPersistenceTests(SimpleTestCase):
    def test_managed_pool_real_processes_import_restart_limits_and_stop(self):
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="reading-hub-workers-test-") as directory:
            Path(directory, "sitecustomize.py").write_text(
                "import socket\n"
                "def deny(*args, **kwargs):\n"
                "    raise OSError('Network forbidden in worker integration test')\n"
                "socket.getaddrinfo = deny\nsocket.socket.connect = deny\n",
                encoding="utf-8",
            )
            environment = {
                **os.environ,
                "READING_HUB_DATA": str(Path(directory, "data")),
                "PYTHONPATH": os.pathsep.join([directory, str(settings.BASE_DIR)]),
            }
            script = """
import os, resource, time
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()
from django.core.management import call_command
from library.models import CrawlCapture, Job, Rendition, WorkerInstance
from library.services import workers
from library.services.catalogue import configured_sites
from library.services.fetch import Response
from library.services.pipeline import enqueue
from library.services.storage import save_response
from library.tests.test_sources import article_html
call_command('migrate', verbosity=0)
workers.save_pool(2, 512)
site = configured_sites().get(host='communistusa.org')
for i in range(20):
    url = f'https://communistusa.org/worker-test-{i}/'
    response = Response(url, article_html(title=f'Worker test {i}'), 'text/html', {})
    CrawlCapture.objects.create(site=site, url=url, response=save_response(response,url))
    enqueue(url)

def wait_for(predicate):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(0.05)
    logs = [(p.name,p.read_text()[-3000:]) for p in workers.worker_directory().glob('*.log')]
    raise AssertionError(logs)

try:
    workers.operate('start')
    wait_for(lambda: Job.objects.exclude(status__in=['ready','failed']).count() == 0)
    assert Job.objects.filter(status='failed').count() == 0, list(Job.objects.values('error'))
    assert Rendition.objects.count() == 20
    assert not Job.objects.filter(worker=None).exists()
    wait_for(lambda: WorkerInstance.objects.filter(
        status='running',applied_memory_mib=512).count()==2)
    for worker in WorkerInstance.objects.all():
        assert workers.process_info(worker)['rss'] > 0
        assert os.getsid(worker.pid) == worker.pid
        assert resource.prlimit(worker.pid, resource.RLIMIT_AS)[0] == 512*1024**2
    first = WorkerInstance.objects.order_by('number').first()
    started = first.started_at
    workers.save_worker(first.pk, 768)
    workers.operate('restart', first.pk)
    wait_for(lambda: WorkerInstance.objects.filter(pk=first.pk,applied_memory_mib=768,
                                                  started_at__gt=started,status='running').exists())
    first.refresh_from_db()
    assert resource.prlimit(first.pid, resource.RLIMIT_AS)[0] == 768*1024**2
    workers.operate('stop', first.pk)
    wait_for(lambda: WorkerInstance.objects.get(pk=first.pk).status == 'stopped')
    wait_for(lambda: not workers.process_info(WorkerInstance.objects.get(pk=first.pk)))
    assert workers.process_info(WorkerInstance.objects.get(number=2))
    workers.operate('start', first.pk)
    wait_for(lambda: WorkerInstance.objects.get(pk=first.pk).status == 'running')
    workers.operate('stop')
    wait_for(lambda: WorkerInstance.objects.filter(status='stopped').count()==2)
    wait_for(lambda: all(p.poll() is not None for p in workers._children.values()))
    print('real worker lifecycle, cached imports, and enforced limits passed')
finally:
    workers.operate('stop')
    for process in list(workers._children.values()):
        try:
            process.wait(timeout=5)
        except __import__('subprocess').TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                env=environment,
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=65,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("enforced limits passed", result.stdout)

    def test_crawler_html_survives_restart_and_formats_without_network(self):
        with tempfile.TemporaryDirectory(prefix="reading-hub-crawl-cache-test-") as directory:
            environment = {**os.environ, "READING_HUB_DATA": directory}
            setup = (
                "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings';"
                "import django; django.setup();"
            )
            scripts = [
                """
from django.core.management import call_command
from unittest.mock import patch
from library.models import CrawlCapture, Snapshot
from library.services.catalogue import configured_sites, change_site
from library.services.fetch import Response
from library.tests.test_sources import ARTICLE, article_html
call_command('migrate', verbosity=0)
site = configured_sites().get(host='communistusa.org')
site.frontier.all().update(status='done')
site.frontier.create(url=ARTICLE, is_article=True)
change_site(site, 'resume', {'fetch_articles': True})
with patch('library.services.fetch.Fetcher.fetch',
           return_value=Response(ARTICLE, article_html(), 'text/html',
                                 {'content-type': 'text/html; charset=utf-8'})):
    call_command('run_import_worker', once=True, verbosity=0)
assert CrawlCapture.objects.count() == 1
assert Snapshot.objects.count() == 0
""",
                """
from unittest.mock import patch
from library.models import CrawlCapture
from library.services.pipeline import enqueue, claim_job, process_job
from library.tests.test_sources import ARTICLE
capture = CrawlCapture.objects.get()
with patch('library.services.pipeline.Fetcher.fetch',
           side_effect=AssertionError('HTML downloaded again')):
    enqueue(ARTICLE)
    version = process_job(claim_job())
assert version is not None
assert version.snapshot.manifest['pages'][0] == capture.response, (
    version.snapshot.manifest['pages'][0], capture.response)
print('persistent crawler cache reused')
""",
            ]
            for script in scripts:
                result = subprocess.run(
                    [sys.executable, "-c", setup + script],
                    env=environment,
                    cwd=settings.BASE_DIR,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("persistent crawler cache reused", result.stdout)

    def test_custom_profile_loads_limits_and_theme_at_startup(self):
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="reading-hub-profile-test-") as directory:
            Path(directory, "custom_profile.py").write_text(
                "from dataclasses import replace\n"
                "from profiles.marxist.site import PROFILE as BASE\n"
                "PROFILE = replace(BASE, key='custom', name='Custom Reading', "
                "theme_css='neutral/theme.css', max_pages=7, max_bytes=1024, "
                "request_timeout=9, request_interval=2)\n",
                encoding="utf-8",
            )
            environment = {
                **os.environ,
                "READING_HUB_DATA": str(Path(directory, "data")),
                "READING_HUB_PROFILE": "custom_profile",
                "PYTHONPATH": os.pathsep.join([directory, str(settings.BASE_DIR)]),
            }
            script = """
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()
from library.profile import get_profile
from library.services.fetch import MAX_PAGES, MAX_BYTES, TIMEOUT
assert get_profile().name == 'Custom Reading'
assert get_profile().theme_css == 'neutral/theme.css'
assert (MAX_PAGES, MAX_BYTES, TIMEOUT) == (7, 1024, 9)
assert get_profile().request_interval == 2
print('custom profile ready')
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=settings.BASE_DIR,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "custom profile ready")

    def test_concurrent_requests_and_process_restart_keep_the_same_cache(self):
        with tempfile.TemporaryDirectory(prefix="reading-hub-process-test-") as directory:
            environment = {**os.environ, "READING_HUB_DATA": directory}

            def execute(script):
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    env=environment,
                    cwd=settings.BASE_DIR,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
                return result.stdout.strip()

            setup = (
                "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings';"
                "import django; django.setup();"
            )
            execute(
                setup + "from django.core.management import call_command;"
                "call_command('migrate',verbosity=0)"
            )
            request_script = (
                setup + "from library.services.pipeline import enqueue;"
                "from library.tests.test_sources import ARTICLE;"
                "print(enqueue(ARTICLE).pk)"
            )
            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", request_script],
                    env=environment,
                    cwd=settings.BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(2)
            ]
            ids = []
            try:
                for process in processes:
                    stdout, stderr = process.communicate(timeout=30)
                    self.assertEqual(process.returncode, 0, stderr)
                    ids.append(stdout.strip())
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=10)
            self.assertEqual(ids[0], ids[1])
            execute(
                setup
                + """
from unittest.mock import patch
from django.core.management import call_command
from library.services.fetch import Response
from library.tests.test_sources import ARTICLE, article_html
with patch('library.services.pipeline.Fetcher.fetch',
           return_value=Response(ARTICLE, article_html(), 'text/html', {})):
    call_command('run_import_worker', once=True)
"""
            )
            result = execute(
                setup
                + """
import json
from unittest.mock import patch
from django.test import Client
from library.models import Document, Job, Rendition
from library.services.pipeline import enqueue
from library.services.storage import read_blob
from library.tests.test_sources import ARTICLE
with patch('library.services.pipeline.Fetcher.fetch', side_effect=AssertionError('Network used')):
    version = enqueue(ARTICLE)
assert read_blob(version.snapshot.manifest['pages'][0]['digest'])
response = Client(HTTP_HOST='localhost').get(f'/versions/{version.pk}/')
print(json.dumps({'documents': Document.objects.count(), 'jobs': Job.objects.count(),
                  'versions': Rendition.objects.count(), 'status': response.status_code,
                  'same_job': str(Job.objects.get().pk)}))
"""
            )
            state = json.loads(result)
            self.assertEqual(
                state,
                {
                    "documents": 1,
                    "jobs": 1,
                    "versions": 1,
                    "status": 200,
                    "same_job": ids[0],
                },
            )
