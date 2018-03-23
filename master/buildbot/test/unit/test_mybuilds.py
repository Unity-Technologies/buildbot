import datetime
import mock
from twisted.trial import unittest
from buildbot.status.web.mybuilds import MybuildsResource


class TestMybuildsResource(unittest.TestCase):
    def setUp(self):
        self.mybuilds = MybuildsResource()

    def get_mocked_status(self):
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
        status.getProjects = mock.Mock(return_value={'Test With Display': config1,
                                                     'Test Without Display': config2})
        return status


    def test_merge_sourcestamps_to_build(self):
        builds_by_ssid = {69: {
            'buildername': u'Elementary Test',
            'builds_id': 131,
            'builds_number': 4,
            'complete': True,
            'complete_at': '2018-03-22 13:07:17+00:00',
            'project': 'Developer Tests',
            'query_params': [],
            'reason': "A build was forced by 'pyflakes pyflakes@localhost': ",
            'slavename': 'build-slave-1',
            'sourcestamps': [],
            'sourcestampsetid': 69,
            'submitted_at': '2018-03-22 13:07:11+00:00'
        }}
        display_repositories = {
            'https://github.com/example/repo.git': 'https://github.com/example/repo.git'
        }
        sourcestamps = [{
            'branch': 'master',
            'codebase': 'fmod',
            'repository': 'https://github.com/example/repo.git',
            'revision': 'bbbbbbbbbbbbaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'short_revision': 'bbbbbbbbbbbb',
            'sourcestampsetid': 69
        }]
        status = self.get_mocked_status()
        status.get_rev_url =\
            lambda rev, repo: "https://github.com/example/repo/commit/bbbbbbbbbbbbaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

        expected_data = [{
            'buildername': u'Elementary Test',
            'builds_id': 131,
            'builds_number': 4,
            'complete': True,
            'complete_at': '2018-03-22 13:07:17+00:00',
            'project': 'Developer Tests',
            'query_params': ['fmod_branch=master'],
            'reason': "A build was forced by 'pyflakes pyflakes@localhost': ",
            'slavename': 'build-slave-1',
            'sourcestamps': [{'branch': 'master',
                              'codebase': 'fmod',
                              'display_repository': 'https://github.com/example/repo.git',
                              'repository': 'https://github.com/example/repo.git',
                              'revision': 'bbbbbbbbbbbbaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                              'revision_url': 'https://github.com/example/repo/commit/bbbbbbbbbbbbaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                              'short_revision': 'bbbbbbbbbbbb',
                              'sourcestampsetid': 69}],
            'sourcestampsetid': 69,
            'submitted_at': '2018-03-22 13:07:11+00:00'
        }]

        builds = self.mybuilds.merge_sourcestamps_to_build(builds_by_ssid, display_repositories,
                                                           sourcestamps, status)

        self.assertEqual(builds, expected_data)


    def test_prepare_builds_by_ssid(self):
        builds =[
            {'sourcestampsetid': 1, 'brid': 11,
             'submitted_at': datetime.datetime(2018, 1, 1),
             'complete_at': datetime.datetime(2018, 1, 2),
            },
            {'sourcestampsetid': 2, 'brid': 22,
             'submitted_at': datetime.datetime(2018, 1, 3),
             'complete_at': datetime.datetime(2018, 1, 4),
            },
        ]
        expected_builds = {
            1: {'sourcestampsetid': 1, 'brid': 11, 'sourcestamps': [], 'query_params': [],
                'submitted_at': str(datetime.datetime(2018, 1, 1)),
                'complete_at': str(datetime.datetime(2018, 1, 2))},
            2: {'sourcestampsetid': 2, 'brid': 22, 'sourcestamps': [], 'query_params': [],
                'submitted_at': str(datetime.datetime(2018, 1, 3)),
                'complete_at': str(datetime.datetime(2018, 1, 4))},
        }

        builds_by_ssid = self.mybuilds.prepare_builds_by_ssid(builds)

        self.assertEqual(sorted(builds_by_ssid.keys()), [1, 2])
        for value in builds_by_ssid.values():
            self.assertIn(value, expected_builds.values())

    def test_prepare_display_repositories(self):
        status = self.get_mocked_status()
        display_repositories = self.mybuilds.prepare_display_repositories(status)

        expected_properties = {
            'https://github.com/stxunityproject/second-test-repository.git': 'https://ono.unity3d.com/unity-extra/fmod',
            'https://github.com/stxunityproject/second-test-repository2.git': 'https://ono.unity3d.com/unity-extra/documentation',
            'https://github.com/stxunityproject/second-test-repository3.git': 'https://github.com/stxunityproject/second-test-repository3.git',
        }
        self.assertEqual(display_repositories, expected_properties)



