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
from datetime import datetime, timedelta

from sqlalchemy.orm import aliased
from twisted.internet import reactor
from buildbot.db import base
from buildbot.db.base import conn_execute
from buildbot.util import epoch2datetime
import sqlalchemy as sa
from buildbot.db.buildrequests import maybeFilterBuildRequestsBySourceStamps, mkdt


class BuildsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst
    NUMBER_OF_REQUESTED_BUILDS = 200

    def getBuild(self, bid):
        def thd(conn):
            tbl = self.db.model.builds
            query = tbl.select(whereclause=(tbl.c.id == bid))
            with conn_execute(conn, query) as res:
                row = res.fetchone()

                rv = None
                if row:
                    rv = self._bdictFromRow(row)
                res.close()
                return rv
        return self.db.pool.do(thd)

    def getBuildsAndResultForRequest(self, brid):
        # @TODO: missing tests
        def thd(conn):
            builds_tbl = self.db.model.builds
            buildrequest_tbl = self.db.model.buildrequests
            q = sa.select([builds_tbl.c.id, builds_tbl.c.number, buildrequest_tbl.c.id.label("brid"), builds_tbl.c.start_time,
                                   builds_tbl.c.finish_time, buildrequest_tbl.c.results],
                                  from_obj= buildrequest_tbl.outerjoin(builds_tbl,
                                                        (buildrequest_tbl.c.id == builds_tbl.c.brid)),
                                  whereclause=(buildrequest_tbl.c.id == brid))
            with conn_execute(conn, q) as res:
                return [ self._bdictFromRow(row)
                         for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def getBuildsForRequest(self, brid):
        def thd(conn):
            tbl = self.db.model.builds
            q = tbl.select(whereclause=(tbl.c.brid == brid))
            with conn_execute(conn, q) as res:
                return [ self._bdictFromRow(row) for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def getBuildNumberForRequest(self, brid):
        # @TODO: missing tests
        def thd(conn):
            tbl = self.db.model.builds
            q = sa.select(columns=[sa.func.max(tbl.c.number).label("number")]).where(tbl.c.brid == brid)
            with conn_execute(conn, q) as res:
                row = res.fetchone()
                if row:
                    return row.number
            return None
        return self.db.pool.do(thd)

    def getBuildNumbersForRequests(self, brids):
        # @TODO: missing tests
        def thd(conn):
            tbl = self.db.model.builds
            q = sa.select(columns=[sa.func.max(tbl.c.number).label("number"), tbl.c.brid])\
                .where(tbl.c.brid.in_(brids))\
                .group_by(tbl.c.number, tbl.c.brid)
            rv = []
            with conn_execute(conn, q) as res:
                rows = res.fetchall()
                if rows:
                    for row in rows:
                        if row.number not in rv:
                            rv.append(row.number)
                res.close()
            return rv
        return self.db.pool.do(thd)

    def addBuild(self, brid, number, slavename=None, _reactor=reactor):
        def thd(conn):
            start_time = _reactor.seconds()
            query = self.db.model.builds.insert()
            conn_args = dict(number=number, brid=brid, slavename=slavename, start_time=start_time,
                             finish_time=None)
            with conn_execute(conn, query, conn_args) as res:
                return res.inserted_primary_key[0]
        return self.db.pool.do(thd)

    def finishBuilds(self, bids, _reactor=reactor):
        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.builds
            now = _reactor.seconds()

            # split the bids into batches, so as not to overflow the parameter
            # lists of the database interface
            remaining = bids
            while remaining:
                batch, remaining = remaining[:100], remaining[100:]
                q = tbl.update(whereclause=(tbl.c.id.in_(batch)))
                with conn_execute(conn, q, finish_time=now):
                    pass
            transaction.commit()
        return self.db.pool.do(thd)

    def finishedMergedBuilds(self, brids, number):
        # @TODO: missing tests
        def thd(conn):
            if len(brids) > 1:
                builds_tbl = self.db.model.builds

                q = sa.select([builds_tbl.c.number, builds_tbl.c.finish_time])\
                    .where(builds_tbl.c.brid == brids[0])\
                    .where(builds_tbl.c.number == number)

                row = None
                with conn_execute(conn, q) as res:
                    row = res.fetchone()

                if row:
                    stmt = builds_tbl.update()\
                        .where(builds_tbl.c.brid.in_(brids))\
                        .where(builds_tbl.c.number==number)\
                        .where(builds_tbl.c.finish_time == None)\
                        .values(finish_time = row.finish_time)

                    with conn_execute(conn, stmt) as res:
                        return res.rowcount

        return self.db.pool.do(thd)

    def getLastsBuildsNumbersBySlave(self, slavename, results=None, num_builds=15):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests
            builds_tbl = self.db.model.builds

            lastBuilds = {}
            maxSearch = num_builds if num_builds < 200 else 200
            resumeBuilds = [9, -1]

            q = sa.select(columns=[buildrequests_tbl.c.id, buildrequests_tbl.c.buildername, builds_tbl.c.number],
                          from_obj=buildrequests_tbl.join(builds_tbl,
                                                          (buildrequests_tbl.c.id == builds_tbl.c.brid)
                                                          & (builds_tbl.c.finish_time != None)))\
                .group_by(buildrequests_tbl.c.id, buildrequests_tbl.c.buildername, builds_tbl.c.number)

            #TODO: support filter by RETRY result
            if results:
                q = sa.select(columns=[buildrequests_tbl.c.id,
                                       buildrequests_tbl.c.buildername,
                                       buildrequests_tbl.c.results,
                                       sa.func.max(builds_tbl.c.number).label("number")],
                          from_obj=buildrequests_tbl.join(builds_tbl,
                                                          (buildrequests_tbl.c.id == builds_tbl.c.brid)
                                                          & (builds_tbl.c.finish_time != None)))\
                    .where(buildrequests_tbl.c.results.in_(results))\
                    .group_by(buildrequests_tbl.c.id, buildrequests_tbl.c.buildername,
                              buildrequests_tbl.c.results)

            q = q.where(buildrequests_tbl.c.mergebrid == None)\
                .where(buildrequests_tbl.c.complete == 1)\
                .where(~buildrequests_tbl.c.results.in_(resumeBuilds))\
                .where(builds_tbl.c.slavename == slavename)\
                .order_by(sa.desc(buildrequests_tbl.c.complete_at)).limit(maxSearch)

            with conn_execute(conn, q) as res:
                rows = res.fetchall()
                if rows:
                    for row in rows:
                        if row.buildername not in lastBuilds:
                            lastBuilds[row.buildername] = [row.number]
                        else:
                            lastBuilds[row.buildername].append(row.number)
                res.close()

            return lastBuilds

        return self.db.pool.do(thd)

    def getLastBuildsNumbers(self, buildername=None, sourcestamps=None, results=None, num_builds=15):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests
            buildsets_tbl = self.db .model.buildsets
            sourcestampsets_tbl = self.db.model.sourcestampsets
            sourcestamps_tbl = self.db.model.sourcestamps
            builds_tbl = self.db.model.builds

            lastBuilds = []
            maxSearch = num_builds if num_builds < 200 else 200
            resumeBuilds = [9, -1]

            q = sa.select(columns=[buildrequests_tbl.c.id, sa.func.max(builds_tbl.c.number).label("number")],
                          from_obj=buildrequests_tbl.join(builds_tbl,
                                                          (buildrequests_tbl.c.id == builds_tbl.c.brid)
                                                          & (builds_tbl.c.finish_time != None))).\
                where(buildrequests_tbl.c.mergebrid == None)\
                .where(~buildrequests_tbl.c.results.in_(resumeBuilds))\
                .where(buildrequests_tbl.c.buildername == buildername)\
                .where(buildrequests_tbl.c.complete == 1)\
                .group_by(buildrequests_tbl.c.id)

            #TODO: support filter by RETRY result
            if results:
                q = sa.select(columns=[buildrequests_tbl.c.id, buildrequests_tbl.c.results,
                                       sa.func.max(builds_tbl.c.number).label("number")],
                          from_obj=buildrequests_tbl.join(builds_tbl,
                                                          (buildrequests_tbl.c.id == builds_tbl.c.brid)
                                                          & (builds_tbl.c.finish_time != None))).\
                    where(buildrequests_tbl.c.mergebrid == None)\
                    .where(buildrequests_tbl.c.buildername == buildername)\
                    .where(buildrequests_tbl.c.results.in_(results))\
                    .where(buildrequests_tbl.c.complete == 1)\
                    .group_by(buildrequests_tbl.c.id, buildrequests_tbl.c.results)

            q = maybeFilterBuildRequestsBySourceStamps(query=q,
                                                       sourcestamps=sourcestamps,
                                                       buildrequests_tbl=buildrequests_tbl,
                                                       buildsets_tbl=buildsets_tbl,
                                                       sourcestamps_tbl=sourcestamps_tbl,
                                                       sourcestampsets_tbl=sourcestampsets_tbl)

            q = q.order_by(sa.desc(buildrequests_tbl.c.complete_at)).limit(maxSearch)

            with conn_execute(conn, q) as res:
                rows = res.fetchall()
                if rows:
                    for row in rows:
                        if row.number not in lastBuilds:
                            lastBuilds.append(row.number)
                res.close()

            return lastBuilds

        return self.db.pool.do(thd)

    def getLastBuildsOwnedBy(self, owner, botmaster):
        if not (isinstance(owner, str) or isinstance(owner, unicode)):
            raise ValueError("Expected owner to be string which is fullname")

        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests
            buildsets_tbl = self.db.model.buildsets
            builds_tbl = self.db.model.builds

            from_clause = buildsets_tbl.join(
                buildrequests_tbl,
                buildrequests_tbl.c.buildsetid == buildsets_tbl.c.id
            ).join(
                builds_tbl,
                builds_tbl.c.brid == buildrequests_tbl.c.id
            )

            q = (
                sa.select([buildrequests_tbl, builds_tbl, buildsets_tbl], use_labels=True)
                .select_from(from_clause)
                .where(buildsets_tbl.c.reason.like('%{}%'.format(owner)))
                .order_by(sa.desc(builds_tbl.c.start_time))
                .limit(self.NUMBER_OF_REQUESTED_BUILDS)
            )

            with conn_execute(conn, q) as res:
                return [self._minimal_bdict(row, botmaster) for row in res.fetchall()]
        return self.db.pool.do(thd)

    def _bdictFromRow(self, row):
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)

        _bdict = dict(
            bid=row.id,
            brid=row.brid,
            number=row.number,
            start_time=mkdt(row.start_time),
            finish_time=mkdt(row.finish_time))
        if 'results' in row.keys():
            _bdict['results'] = row.results
        return _bdict

    @staticmethod
    def _minimal_bdict(row, botmaster):
        return dict(
            buildername=row.buildrequests_buildername,
            complete=bool(row.buildrequests_complete),
            builds_id=row.builds_id,
            builds_number=row.builds_number,
            reason=row.buildsets_reason,
            project=botmaster.getBuilderConfig(row.buildrequests_buildername).project,
            slavename=row.builds_slavename,
            submitted_at=mkdt(row.buildrequests_submitted_at),
            complete_at=mkdt(row.buildrequests_complete_at)
        )
