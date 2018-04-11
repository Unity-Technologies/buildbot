import mock
from twisted.trial import unittest
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
