from operator import itemgetter
from twisted.internet import defer

from buildbot.status.web.base import HtmlResource
from buildbot.config import MasterConfig

class MybuildsResource(HtmlResource):
    pageTitle = "MyBuilds"

    @defer.inlineCallbacks
    def content(self, req, cxt):
        master = self.getBuildmaster(req)
        username = cxt['authz'].getUsernameFull(req)
        builds = yield master.db.builds.getLastBuildsOwnedBy(
            username,
            master.status.botmaster,
            master.config.myBuildDaysCount,
        )

        builds_by_ssid = {}
        for row in builds:
            row['sourcestamps'] = []
            row['query_params'] = []
            builds_by_ssid[row['sourcestampsetid']] = row

        sourcestamps = yield master.db.sourcestamps.getSourceStampsForManyIds(builds_by_ssid.keys())

        for row in sourcestamps:
            build = builds_by_ssid[row['sourcestampsetid']]
            query_param = "%s_branch=%s" % (row['codebase'], row['branch'])
            build['query_params'].append(query_param)
            build['sourcestamps'].append(row)

        cxt['builds'] = sorted(builds_by_ssid.values(), key=itemgetter('builds_id'), reverse=True)
        cxt['days_count'] = master.config.myBuildDaysCount
        template = req.site.buildbot_service.templates.get_template("mybuilds.html")
        template.autoescape = True
        defer.returnValue(template.render(**cxt))
