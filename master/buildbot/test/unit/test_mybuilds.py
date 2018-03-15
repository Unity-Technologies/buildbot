import mock
from twisted.trial import unittest
from buildbot.status.results import RESULT_TO_CSS, Results
from buildbot.status.web.mybuilds import MybuildsResource

class TestMybuildsResource(unittest.TestCase):
    def setUp(self):
        self.mybuilds = MybuildsResource()

    def test_prepare_builds_by_ssid(self):
        builds =[
            {'sourcestampsetid': 1, 'brid': 11},
            {'sourcestampsetid': 2, 'brid': 22},
        ]
        expected_builds = {
            1: {'sourcestampsetid': 1, 'brid': 11, 'sourcestamps': [], 'query_params': []},
            2: {'sourcestampsetid': 2, 'brid': 22, 'sourcestamps': [], 'query_params': []},
        }

        builds_by_ssid = self.mybuilds.prepare_builds_by_ssid(builds)

        self.assertEqual(sorted(builds_by_ssid.keys()), [1, 2])
        for value in builds_by_ssid.values():
            self.assertIn(value, expected_builds.values())

    def test_prepare_display_repositories(self):
        config1 = mock.Mock()
        config1.codebases = [
            {'fmod1': {'project': 'general', 'display_name': 'fmod', 'branch': ['HEAD', 'trunk'],
                       'repository': 'https://github.com/stxunityproject/second-test-repository.git',
                       'display_repository': 'https://ono.unity3d.com/unity-extra/fmod'}
            },
            {'fmod2': {'project': 'general', 'display_name': 'katana', 'branch': 'HEAD',
                       'repository': 'https://github.com/stxunityproject/second-test-repository2.git',
                       'display_repository': 'https://ono.unity3d.com/unity-extra/documentation'}
            },
        ]
        config2 = mock.Mock()
        config2.codebases = [
            {'fmod3': {'project': 'general', 'display_name': 'fmod', 'branch': 'master',
                       'repository': 'https://github.com/stxunityproject/second-test-repository3.git'}
            },
        ]
        status = mock.Mock()
        status.getProjects = mock.Mock(return_value={'Test With Display': config1, 'Test Without Display': config2})

        display_repositories = self.mybuilds.prepare_display_repositories(status)

        expected_properties = {
            'https://github.com/stxunityproject/second-test-repository.git': 'https://ono.unity3d.com/unity-extra/fmod',
            'https://github.com/stxunityproject/second-test-repository2.git': 'https://ono.unity3d.com/unity-extra/documentation',
            'https://github.com/stxunityproject/second-test-repository3.git': 'https://github.com/stxunityproject/second-test-repository3.git',
        }
        self.assertEqual(display_repositories, expected_properties)

    def test_add_css_classes_to_results(self):
        builds = [{'results': i} for i in range(-1, 12)]
        expected_builds = [
            {'results': -1, 'result_css_class': 'running',                'result_name': 'running'},
            {'results':  0, 'result_css_class': 'success',                'result_name': 'success'},
            {'results':  1, 'result_css_class': 'warnings',               'result_name': 'warnings'},
            {'results':  2, 'result_css_class': 'failure',                'result_name': 'failure'},
            {'results':  3, 'result_css_class': 'skipped',                'result_name': 'skipped'},
            {'results':  4, 'result_css_class': 'exception',              'result_name': 'exception'},
            {'results':  5, 'result_css_class': 'retry',                  'result_name': 'retry'},
            {'results':  6, 'result_css_class': 'canceled',               'result_name': 'canceled'},
            {'results':  7, 'result_css_class': 'not-rebuilt',            'result_name': 'not-rebuilt'},
            {'results':  8, 'result_css_class': 'dependency-failure',     'result_name': 'dependency-failure'},
            {'results':  9, 'result_css_class': 'waiting-for-dependency', 'result_name': 'resume'},
            {'results': 10, 'result_css_class': 'not-started',            'result_name': 'merged'},
            {'results': 11, 'result_css_class': 'interrupted',            'result_name': 'interrupted'},
        ]

        self.mybuilds.add_css_classes_to_results(builds)

        self.assertEqual(builds, expected_builds)
