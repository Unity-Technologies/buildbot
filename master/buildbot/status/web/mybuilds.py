from itertools import chain
from operator import itemgetter
from twisted.internet import defer

from buildbot.status.web.base import HtmlResource


class MybuildsResource(HtmlResource):
    pageTitle = "MyBuilds"

    @defer.inlineCallbacks
    def content(self, req, cxt):
        master = self.getBuildmaster(req)
        status = master.getStatus()
        display_repositories = self.prepare_display_repositories(status)

        builds = yield master.db.builds.getLastBuildsOwnedBy(
            cxt['authz'].getUserInfo(cxt['authz'].getUsername(req))['uid'],
            master.status.botmaster,
            master.config.myBuildDaysCount,
        )

        builds_by_ssid = self.prepare_builds_by_ssid(builds)
        sourcestamps = yield master.db.sourcestamps.getSourceStampsForManyIds(builds_by_ssid.keys())

        for row in sourcestamps:
            build = builds_by_ssid[row['sourcestampsetid']]
            query_param = "%s_branch=%s" % (row['codebase'], row['branch'])
            build['query_params'].append(query_param)

            row['revision_url'] = status.get_rev_url(row['revision'], row['repository'])
            row['display_repository'] = display_repositories.get(row['repository'], row['repository'])

            build['sourcestamps'].append(row)

        cxt['builds'] = sorted(builds_by_ssid.values(), key=itemgetter('builds_id'), reverse=True)
        cxt['days_count'] = master.config.myBuildDaysCount
        template = req.site.buildbot_service.templates.get_template("mybuilds.html")
        template.autoescape = True
        defer.returnValue(template.render(**cxt))

    @staticmethod
    def prepare_display_repositories(status):
        """ return {repository: display_repository} from all projects"""
        display_repositories = {}
        flatten_codebases = chain(*map(lambda x: x.codebases, status.getProjects().values()))
        properties = map(lambda y: y.values(), flatten_codebases)
        for prop in chain(*properties):
            display_repository = prop.get('display_repository', prop['repository'])
            display_repositories[prop['repository']] = display_repository
        return display_repositories

    @staticmethod
    def prepare_builds_by_ssid(builds):
        builds_by_ssid = {}
        for row in builds:
            row['sourcestamps'] = []
            row['query_params'] = []
            builds_by_ssid[row['sourcestampsetid']] = row
        return builds_by_ssid
