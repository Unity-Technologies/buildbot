from twisted.trial import unittest
from buildbot.changes.custom.hgpoller import HgPoller
from buildbot.changes.custom.gitpoller import GitPoller
from twisted.internet import defer, utils
from mock import Mock
from buildbot.util import datetime2epoch
from buildbot.changes.changes import Change

class TestCustomPoller(unittest.TestCase):

    def mockCommand(self, command):
        for cmd in self.expected_commands:
            if command == cmd['command']:
                return cmd['stdout']
        return ''

    def getProcessOutput(self, executable, args=(), env={}, path=None, reactor=None,
                 errortoo=0):
        return self.mockCommand(args)

    def _dovccmd(self, command, args, path=None):
        return self.mockCommand([command] + args)

    def checkChangesList(self, changes_added, expected_changes):
        self.assertEqual(len(changes_added), len(expected_changes))
        for i in range(len(changes_added)):
            self.assertEqual(changes_added[i].asDict(), expected_changes[i].asDict())

    def setup_lastRev(self, poller):
        poller.lastRev = {"1.0/dev": "835be7494fb405bbe2605e1075102790e604938a",
                          "stable": "05bbe2605e1075102790e6049384e1de6bb28b28",
                          "1.0/devOld": "1:625be7494fb5", # for testing backwards compatibility with db
                          "stableOld": "3:05bbe2605e10" # for testing backwards compatibility with db
        }

    def setup(self, poller):
        poller._absWorkdir = lambda: "dir/"
        self.setup_lastRev(poller)
        poller.master = Mock()
        self.changes_added = []

        def addChange(files=None, comments=None, author=None, revision=None,
                      when_timestamp=None, branch=None, repository='', codebase='',
                      category='', project='', src=None):
            self.changes_added.append(Change(revision=revision, files=files,
                                 who=author, branch=branch, comments=comments,
                                 when=datetime2epoch(when_timestamp), repository=repository, codebase=codebase))
            return defer.succeed(None)

        poller.master.addChange = addChange
        self.patch(utils, "getProcessOutput", self.getProcessOutput)

    def getExpectedChanges(self, repository, bookmark=True):
        return [Change(revision=u'5553a6194a6393dfbec82f96654d52a76ddf844d', files=None,
                       who=u'dev3 <dev3@mail.com>', branch=u'1.0/dev', comments=u'list of changes3',
                       when=1421583649, category=None, project='',
                       repository=repository, codebase=''),
                Change(revision=u'b2e48cbab3f0753f99db833acff6ca18096854bd', files=None,
                       who=u'dev2 <dev2@mail.com>', branch=u'1.0/dev', comments=u'list of changes2',
                       when=1421667112, category=None, project='',
                       repository=repository, codebase=''),
                Change(revision=u'117b9a27b5bf65d7e7b5edb48f7fd59dc4170486', files=None,
                       who=u'dev1 <dev1@mail.com>', branch=u'1.0/dev', comments=u'list of changes1',
                       when=1421667230, repository=repository, codebase=''),
                Change(revision=u'70fc4de2ff3828a587d80f7528c1b5314c51550e7', files=None,
                       who=u'dev4 <dev4@mail.com>', branch=u'trunkbookmark' if bookmark else u'trunk',
                       comments=u'list of changes4', when=1422983233,
                       category=None, project='', repository=repository,
                       codebase='')
                ]

    def getExpectedChangesHg(self, repository, bookmark=True):
        return self.getExpectedChanges(repository, bookmark) + [
                # backwards compatibility
                Change(revision=u'68475k937dj69dk20567845jh9456726153hv47g7', files=None,
                       who=u'dev5 <dev5@mail.com>', branch=u'1.0/devOld', comments=u'list of changes5',
                       when=1421667231, category=None, project='',
                       repository=repository, codebase=''),
                ]

    def add_backwards_compatibility_with_db_commands(self):
        self.expected_commands.append({'command': ['heads', '1.0/devOld', '--template={node}\n'],
                                       'stdout': defer.succeed('68475k937dj69dk20567845jh9456726153hv47g7')})

        self.expected_commands.append({'command': ['log', '-b', '1.0/devOld', '-r',
                                                   '625be7494fb5:68475k937dj69dk20567845jh9456726153hv47g7',
                                                   '--template={node}\\n'],
                                       'stdout': defer.succeed('68475k937dj69dk20567845jh9456726153hv47g7\n')})

        self.expected_commands.append({'command': ['log', '-r', '68475k937dj69dk20567845jh9456726153hv47g7',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1421667231 -3600\ndev5 <dev5@mail.com>\nlist of changes5')})

    @defer.inlineCallbacks
    def test_mercurialPollsAnyBranch(self):
        poller = HgPoller(repourl='http://hg.repo.org/src',
                                   branches={'include': [r'.*'],
                                             'exclude': [r'default', '5.0/*']},
                                   workdir='hgpoller-mercurial', pollInterval=60)


        self.setup(poller)
        self.expected_commands = [{'command': ['log', '-r',
                                               'last(:tip,10000) and head() and not closed() or bookmark()',
                                               '--template', '{branch} {bookmarks} {node}\n'],
                             'stdout': 'default defaultbookmark 5cf71f97924e345114567b95a652a1s324d7b5bf\n' +
                                       '5.0/dev  960963s2fde73453564f64675y667k34e6h4d890\n' +
                                       '1.0/dev  117b9a27b5bf65d7e7b5edb48f7fd59dc4170486\n' +
                                       'trunk  trunkbookmark 70fc4de2ff3828a587d80f7528c1b5314c51550e7\n' +
                                       '1.0/devOld  68475k937dj69dk20567845jh9456726153hv47g7\n' # backwards compatibility
                                }]

        yield poller._processBranches(None)

        self.assertEqual(poller.currentRev, {'1.0/dev': '117b9a27b5bf65d7e7b5edb48f7fd59dc4170486',
                                             'trunkbookmark': '70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                             '1.0/devOld': '68475k937dj69dk20567845jh9456726153hv47g7' # backwards compatibility
                                             })

        self.expected_commands.append({'command': ['heads', '1.0/dev', '--template={node}\n'],
                                       'stdout': defer.succeed('117b9a27b5bf65d7e7b5edb48f7fd59dc4170486')})

        self.expected_commands.append({'command': ['heads', 'trunkbookmark', '--template={node}\n'],
                                       'stdout': defer.succeed('70fc4de2ff3828a587d80f7528c1b5314c51550e7')})

        self.expected_commands.append({'command': ['log', '-b', 'trunkbookmark', '-r',
                                                   '70fc4de2ff3828a587d80f7528c1b5314c51550e7:' +
                                                   '70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                                   '--template={node}\\n'],
                                       'stdout': defer.succeed('70fc4de2ff3828a587d80f7528c1b5314c51550e7')})

        self.expected_commands.append({'command': ['log', '-b', '1.0/dev', '-r',
                                                   '835be7494fb405bbe2605e1075102790e604938a:117b9a27b5bf65d7e7b5edb48f7fd59dc4170486',
                                                   '--template={node}\\n'],
                                       'stdout': defer.succeed('5553a6194a6393dfbec82f96654d52a76ddf844d\n' +
                                                               'b2e48cbab3f0753f99db833acff6ca18096854bd\n' +
                                                               '117b9a27b5bf65d7e7b5edb48f7fd59dc4170486\n')})

        self.add_backwards_compatibility_with_db_commands()

        self.expected_commands.append({'command': ['log', '-r', '70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1422983233 -3600\ndev4 <dev4@mail.com>\nlist of changes4')})

        self.expected_commands.append({'command': ['log', '-r', '5553a6194a6393dfbec82f96654d52a76ddf844d',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1421583649 -3600\ndev3 <dev3@mail.com>\nlist of changes3')})

        self.expected_commands.append({'command': ['log', '-r', 'b2e48cbab3f0753f99db833acff6ca18096854bd',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1421667112 -3600\ndev2 <dev2@mail.com>\nlist of changes2')})

        self.expected_commands.append({'command': ['log', '-r', '117b9a27b5bf65d7e7b5edb48f7fd59dc4170486',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1421667230 -3600\ndev1 <dev1@mail.com>\nlist of changes1')})

        yield poller._processChangesAllBranches(None)

        self.assertEqual(poller.lastRev, {'1.0/dev': '117b9a27b5bf65d7e7b5edb48f7fd59dc4170486',
                                          'trunkbookmark': '70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                          '1.0/devOld': '68475k937dj69dk20567845jh9456726153hv47g7',})

        expected_changes = self.getExpectedChangesHg(repository='http://hg.repo.org/src')

        changes_added = sorted(self.changes_added, key=lambda change: change.when)
        expected_changes = sorted(expected_changes, key=lambda change : change.when)

        self.checkChangesList(changes_added, expected_changes)


    @defer.inlineCallbacks
    def test_gitPollsAnyBranch(self):
        poller = GitPoller(repourl='https://github.com/usr/repo.git',
                                    workdir='gitpoller-repo', branches={'include': [r'.*'],
                                                                        'exclude': [r'origin/default', 'origin/5.0/*']},
                                    pollinterval=30)
        self.setup(poller)

        poller._dovccmd = self._dovccmd
        poller.lastRev = {"1.0/dev": "835be7494fb4b473bcc0bbefb45d6b3d564f664",
                          "stable": "5fc745a34fb9ec8ded7959aad3a1ed69c92d5742"}

        self.expected_commands = [{'command': ['branch', '-r'],
                             'stdout': 'origin/5.0/dev\n' +
                                       'origin/1.0/dev\n' +
                                       'origin/default\n' +
                                       'origin/HEAD -> trunk\n'
                                  }]

        yield poller._processBranches(None)

        self.assertEqual(poller.currentBranches, ['origin/1.0/dev', 'trunk'])

        self.expected_commands.append({'command': ['rev-parse', 'trunk'],
                                       'stdout': defer.succeed('70fc4de2ff3828a587d80f7528c1b5314c51550e7')})

        self.expected_commands.append({'command': ['rev-parse', 'origin/1.0/dev'],
                                       'stdout': defer.succeed('117b9a27b5bf65d7e7b5edb48f7fd59dc4170486')})

        self.expected_commands.append({'command': ['log', '--format=%H', '70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                                   '-1', '--'],
                                       'stdout': defer.succeed('70fc4de2ff3828a587d80f7528c1b5314c51550e7')})

        def getExpectedCmd(revision, when, developer, comments):
            return [{'command': ['log', '--no-walk', '--format=%ct', revision, '--'],
                     'stdout': defer.succeed(when)},
                    {'command': ['log', '--no-walk', '--format=%aN <%aE>', revision, '--'],
                     'stdout': defer.succeed(developer)},
                    {'command': ['log', '--no-walk', '--format=%s%n%b', revision, '--'],
                     'stdout': defer.succeed(comments)}]

        self.expected_commands += getExpectedCmd('70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                                 1422983233,
                                                 'dev4 <dev4@mail.com>',
                                                 'list of changes4')

        self.expected_commands\
            .append(
            {'command':
                 ['log', '--format=%H', '--ancestry-path',
                  '835be7494fb4b473bcc0bbefb45d6b3d564f664..117b9a27b5bf65d7e7b5edb48f7fd59dc4170486', '--'],
             'stdout': defer.succeed('117b9a27b5bf65d7e7b5edb48f7fd59dc4170486\n' +
                                     'b2e48cbab3f0753f99db833acff6ca18096854bd\n' +
                                     '5553a6194a6393dfbec82f96654d52a76ddf844d\n')})

        self.expected_commands += getExpectedCmd('117b9a27b5bf65d7e7b5edb48f7fd59dc4170486',
                                                 1421667230,
                                                 'dev1 <dev1@mail.com>',
                                                 'list of changes1')

        self.expected_commands += getExpectedCmd('b2e48cbab3f0753f99db833acff6ca18096854bd',
                                                 1421667112,
                                                 'dev2 <dev2@mail.com>',
                                                 'list of changes2')

        self.expected_commands += getExpectedCmd('5553a6194a6393dfbec82f96654d52a76ddf844d',
                                                 1421583649,
                                                 'dev3 <dev3@mail.com>',
                                                 'list of changes3')

        yield poller._processChangesAllBranches(None)

        self.assertEqual(poller.lastRev, {'1.0/dev': '117b9a27b5bf65d7e7b5edb48f7fd59dc4170486',
                                          'trunk': '70fc4de2ff3828a587d80f7528c1b5314c51550e7'})

        expected_changes = self.getExpectedChanges(repository='https://github.com/usr/repo.git', bookmark=False)

        self.checkChangesList(self.changes_added, expected_changes)
