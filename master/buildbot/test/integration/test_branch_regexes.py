import unittest

from buildbot.config import REGEX_BRANCHES, TAG_AS_BRANCH_REGEX
from buildbot.status.web import base


class TestBranchRegexes(unittest.TestCase):
    def setUp(self):
        self.regex_branches = REGEX_BRANCHES
        self.tag_as_branch_regex = TAG_AS_BRANCH_REGEX

    ### filter_tags_by_codebases ###

    def test_filter_tags_by_codebases_many_tags(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'unity': '2018.2/'}
        expected_tags = ['QV', 'Unstable']

        filtered_tags = base.filter_tags_by_codebases(tags, codebases, self.tag_as_branch_regex,
                                                      self.regex_branches)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_many_cb(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'unity': 'trunk/', 'mod': '2018.2/'}
        expected_tags = ['ABV', 'QV', 'Unstable']

        filtered_tags = base.filter_tags_by_codebases(tags, codebases, self.tag_as_branch_regex,
                                                      self.regex_branches)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_simple_unstable(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'unity': 'trunk/'}
        expected_tags = ['ABV', 'Unstable']

        filtered_tags = base.filter_tags_by_codebases(tags, codebases, self.tag_as_branch_regex,
                                                      self.regex_branches)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_foreign_unstable(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV', '2018.2-QV-Unstable']
        codebases = {'unity': 'trunk/'}
        expected_tags = ['ABV']

        filtered_tags = base.filter_tags_by_codebases(tags, codebases, self.tag_as_branch_regex,
                                                      self.regex_branches)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_empty_cb(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {}
        expected_tags = sorted(tags)

        filtered_tags = base.filter_tags_by_codebases(tags, codebases, self.tag_as_branch_regex,
                                                      self.regex_branches)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_uknown_branch(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'foo': '2019.2/'}  # not unity, good pattern
        expected_tags = ['ABV', 'Unstable']  # use Trunk tags

        filtered_tags = base.filter_tags_by_codebases(tags, codebases, self.tag_as_branch_regex,
                                                      self.regex_branches)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_unity_cb(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'unity': 'foo/'}  # unity, wrong pattern
        expected_tags = ['ABV', 'Unstable']  # use Trunk tags

        filtered_tags = base.filter_tags_by_codebases(tags, codebases, self.tag_as_branch_regex,
                                                      self.regex_branches)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_wrong_cb_and_branch(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'foo': 'bar/'}  # not unity, wrong pattern
        expected_tags = sorted(tags)  # return original tags

        filtered_tags = base.filter_tags_by_codebases(tags, codebases, self.tag_as_branch_regex,
                                                      self.regex_branches)

        self.assertEqual(expected_tags, filtered_tags)

    ### get_query_branches_for_codebases ###

    def test_get_query_branches_for_codebases_good_case(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'foo': '2018.2/'}
        expected_branches = {'2018.2'}

        branches = base.get_query_branches_for_codebases(tags, codebases, self.regex_branches)

        self.assertEqual(branches, expected_branches)

    def test_get_query_branches_for_codebases_unity_key(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'unity': 'bar/'}
        expected_branches = {'trunk'}

        branches = base.get_query_branches_for_codebases(tags, codebases, self.regex_branches)

        self.assertEqual(branches, expected_branches)

    def test_get_query_branches_for_codebases_wrong_codebase(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'foo': 'bar/'}
        expected_branches = set()

        branches = base.get_query_branches_for_codebases(tags, codebases, self.regex_branches)

        self.assertEqual(branches, expected_branches)

    def test_get_query_branches_for_codebases_not_tags(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'foo': '2019.2/'}
        expected_branches = {'trunk'}

        branches = base.get_query_branches_for_codebases(tags, codebases, self.regex_branches)

        self.assertEqual(branches, expected_branches)
