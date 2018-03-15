# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members
import mock

from twisted.trial import unittest
from buildbot.status.web.base import path_to_build_by_params, path_to_builder_by_params


class StubRequest(object):
    def __init__(self, args):
        self.args = args
        self.prepath = None


class Path(unittest.TestCase):
    @mock.patch('buildbot.status.web.base.path_to_builders')
    def test_path_to_builder_with_params(self, mock_path_to_builders):
        mock_path_to_builders.return_value = 'test-path-to-builder'
        stub_request = StubRequest(args={'fmod_branch': ['master']})
        expected_url = 'test-path-to-builder/test-builder?fmod_branch=master'

        url = path_to_builder_by_params(stub_request, 'test-project', 'test-builder')

        self.assertEqual(url, expected_url)

    @mock.patch('buildbot.status.web.base.path_to_builders')
    def test_path_to_builder_with_multiple_params(self, mock_path_to_builders):
        mock_path_to_builders.return_value = 'test-path-to-builder'
        stub_request = StubRequest(args={'fmod_branch': ['master'], 'doc_branch': 'release_v2.3.15'})
        expected_url = 'test-path-to-builder/test-builder?fmod_branch=master&doc_branch=release_v2.3.15'

        url = path_to_builder_by_params(stub_request, 'test-project', 'test-builder')

        self.assertEqual(url, expected_url)

    @mock.patch('buildbot.status.web.base.path_to_builders')
    def test_path_to_builder_without_params(self, mock_path_to_builders):
        mock_path_to_builders.return_value = 'test-path-to-builder'
        stub_request = StubRequest(args={})
        expected_url = 'test-path-to-builder/test-builder'

        url = path_to_builder_by_params(stub_request, 'test-project', 'test-builder')

        self.assertEqual(url, expected_url)

    @mock.patch('buildbot.status.web.base.path_to_builders')
    def test_path_to_builder_without_codebases(self, mock_path_to_builders):
        mock_path_to_builders.return_value = 'test-path-to-builder'
        stub_request = StubRequest(args={'fmod_branch': ['master']})
        expected_url = 'test-path-to-builder/test-builder'

        url = path_to_builder_by_params(stub_request, 'test-project', 'test-builder', False)

        self.assertEqual(url, expected_url)

    @mock.patch('buildbot.status.web.base.path_to_builder_by_params')
    def test_path_to_build_with_params(self, mock_path_to_builder_by_params):
        mock_path_to_builder_by_params.return_value = 'test-url'
        stub_request = StubRequest(args={'fmod_branch': ['master']})
        expected_url = 'test-url/builds/16?fmod_branch=master'

        url = path_to_build_by_params(stub_request, 'test-builder', 16, 'test-project')

        self.assertEqual(url, expected_url)

    @mock.patch('buildbot.status.web.base.path_to_builder_by_params')
    def test_path_to_build_with_multiple_params(self, mock_path_to_builder_by_params):
        mock_path_to_builder_by_params.return_value = 'test-url'
        stub_request = StubRequest(args={'fmod_branch': ['master'], 'doc_branch': 'release_v2.3.15'})
        expected_url = 'test-url/builds/16?fmod_branch=master&doc_branch=release_v2.3.15'

        url = path_to_build_by_params(stub_request, 'test-builder', 16, 'test-project')

        self.assertEqual(url, expected_url)

    @mock.patch('buildbot.status.web.base.path_to_builder_by_params')
    def test_path_to_build_without_params(self, mock_path_to_builder_by_params):
        mock_path_to_builder_by_params.return_value = 'test-url'
        stub_request = StubRequest(args={})
        expected_url = 'test-url/builds/16'

        url = path_to_build_by_params(stub_request, 'test-builder', 16, 'test-project')

        self.assertEqual(url, expected_url)

    @mock.patch('buildbot.status.web.base.path_to_builder_by_params')
    def test_path_to_build_without_codebases(self, mock_path_to_builder_by_params):
        mock_path_to_builder_by_params.return_value = 'test-url'
        stub_request = StubRequest(args={'fmod_branch': ['master']})
        expected_url = 'test-url/builds/16'

        url = path_to_build_by_params(stub_request, 'test-builder', 16, 'test-project', False)

        self.assertEqual(url, expected_url)
