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

"""
Support for buildsets in the database
"""

import sqlalchemy as sa
from twisted.internet import reactor
from buildbot.util import json
from buildbot.db import base
from buildbot.db.base import conn_execute
from buildbot.util import epoch2datetime, datetime2epoch
from buildbot.process.buildrequest import Priority

class BsDict(dict):
    pass

class BuildsetsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def addBuildset(self, sourcestampsetid, reason, properties, triggeredbybrid=None,
                    builderNames=None, external_idstring=None, brDictsToMerge=None,
                    _reactor=reactor, _master_objectid=None):
        """
        :param sourcestampsetid:
        :param reason:
        :param properties:
        :param triggeredbybrid:
        :param builderNames:
        :param external_idstring:
        :param dict(string:BrDict) brDictsToMerge:
            Dictionary of build request dictionaries to merge into.

            Maps a buildername (for new build requests being added) to a build request
            we want to merge into.

            This function assumes that all of there merge targets are currently running
            and that they will not finish while this function is running (ie, this
            function is not thread-safe and assumes it runs inside a lock)
        :return:
        """
        if brDictsToMerge is None:
            brDictsToMerge = {}

        def thd(conn):
            priority = Priority.Default
            buildsets_tbl = self.db.model.buildsets
            submitted_at = _reactor.seconds()

            reason_val = self.truncateColumn(buildsets_tbl.c.reason, reason)
            self.check_length(buildsets_tbl.c.reason, reason_val)
            self.check_length(buildsets_tbl.c.external_idstring,
                    external_idstring)

            transaction = conn.begin()

            # insert the buildset itself
            query = buildsets_tbl.insert()
            conn_args = dict(
                sourcestampsetid=sourcestampsetid, submitted_at=submitted_at,
                reason=reason_val, complete=0, complete_at=None, results=-1,
                external_idstring=external_idstring)
            with conn_execute(conn, query, conn_args) as res:
                bsid = res.inserted_primary_key[0]

            # add any properties
            if properties:
                bs_props_tbl = self.db.model.buildset_properties
                if 'priority' in properties:
                    priority_property = properties.get('priority')[0]
                    priority = priority_property if priority_property \
                                                    and int(priority_property) > 0 else Priority.Default

                inserts = [
                    dict(buildsetid=bsid, property_name=k,
                         property_value=json.dumps([v,s]))
                    for k,(v,s) in properties.iteritems() ]
                for i in inserts:
                    self.check_length(bs_props_tbl.c.property_name,
                                      i['property_name'])
                with conn_execute(conn, bs_props_tbl.insert(), inserts):
                    pass

            # and finish with a build request for each builder.  Note that
            # sqlalchemy and the Python DBAPI do not provide a way to recover
            # inserted IDs from a multi-row insert, so this is done one row at
            # a time.
            brids = {}
            br_tbl = self.db.model.buildrequests
            startbrid = triggeredbybrid
            if triggeredbybrid is not None:
                q = sa.select([br_tbl.c.triggeredbybrid, br_tbl.c.startbrid]) \
                    .where(br_tbl.c.id == triggeredbybrid)

                with conn_execute(conn, q) as res:
                    row = res.fetchone()
                    if row and (row.startbrid is not None):
                        startbrid = row.startbrid

            ins = br_tbl.insert()
            for buildername in builderNames:
                self.check_length(br_tbl.c.buildername, buildername)

                # If this builder is being merged, figure out what to merge into
                mergeBrDict = brDictsToMerge.get(buildername, None)
                if mergeBrDict:
                    # Set our merge target
                    mergebrid = brDictsToMerge[buildername]['brid']

                    # And reuse artifacts. `artifactbrid` and `mergebrid` will almost
                    # always be the same, except for cases where we are merging against
                    # a build that reused previous artifacts
                    artifactbrid = brDictsToMerge[buildername]['artifactbrid'] or mergebrid
                else:
                    mergebrid = artifactbrid = None

                # Add the buildrequest to the database
                conn_args = dict(buildsetid=bsid, buildername=buildername, priority=priority,
                                 complete=0, results=-1,
                                 submitted_at=submitted_at, complete_at=None,
                                 triggeredbybrid=triggeredbybrid, startbrid=startbrid,
                                 mergebrid=mergebrid, artifactbrid=artifactbrid)
                with conn_execute(conn, ins, conn_args) as res:
                    brids[buildername] = res.inserted_primary_key[0]

            # Do the rest of the merge process for merged builds
            # Check if we have anything, because SQLAlchemy breaks if you try inserting an empty
            # list of values
            if brDictsToMerge:
                current_time = _reactor.seconds()

                # Register breq as claimed
                q = self.db.model.buildrequest_claims.insert()
                conn_args = [dict(brid=brids[buildername], objectid=_master_objectid,
                                  claimed_at=current_time)
                             for (buildername, _mergeBrDict) in brDictsToMerge.iteritems()]
                with conn_execute(conn, q, conn_args):
                    pass

                # If we are merging against a running request, register a build for this breq
                # Again, check if there are merge target with build numbers, otherwise SQLAlchemy
                # will break when inserting empty list of values
                brDictsWithBuilds = {
                    buildername: mergeBrDict
                    for (buildername, mergeBrDict) in brDictsToMerge.iteritems()
                    if mergeBrDict['build_number']
                }
                if brDictsWithBuilds:
                    q = self.db.model.builds.insert()
                    conn_args = [dict(number=mergeBrDict['build_number'], brid=brids[buildername],
                                      start_time=current_time, finish_time=None)
                                 for (buildername, mergeBrDict) in brDictsWithBuilds.iteritems()]
                    with conn_execute(conn, q, conn_args):
                        pass

            transaction.commit()

            return (bsid, brids)
        return self.db.pool.do(thd)

    def completeBuildset(self, bsid, results, complete_at=None,
                                _reactor=reactor):
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = _reactor.seconds()

        def thd(conn):
            tbl = self.db.model.buildsets
            def update():
                q = tbl.update(whereclause=(
                    (tbl.c.id == bsid) &
                    ((tbl.c.complete_at == None) | (tbl.c.complete != 1))))
                conn_kwargs = dict(
                    complete=1,
                    results=results,
                    complete_at=complete_at,
                )
                with conn_execute(conn, q, **conn_kwargs) as res:
                    return (res.rowcount > 0)

            # maybe another build completed the buildset
            def checkupdated():
                q = tbl.select(whereclause=((tbl.c.id == bsid)
                               & (tbl.c.complete==1) & (tbl.c.complete_at != None)))
                with conn_execute(conn, q) as res:
                    row = res.fetchone()
                    res.close()
                    if not row:
                        raise KeyError
                    
            if update():               
                return
            else:
                checkupdated()

        return self.db.pool.do(thd)

    def getBuildset(self, bsid):
        def thd(conn):
            bs_tbl = self.db.model.buildsets
            q = bs_tbl.select(whereclause=(bs_tbl.c.id == bsid))
            with conn_execute(conn, q) as res:
                row = res.fetchone()
                if not row:
                    return None
                return self._row2dict(row)
        return self.db.pool.do(thd)

    def getBuildsetsByIds(self, bsids):
        def thd(conn):
            bs_tbl = self.db.model.buildsets
            q = bs_tbl.select(whereclause=(bs_tbl.c.id.in_(bsids)))
            build_sets = {}
            with conn_execute(conn, q) as res:
                for row in res.fetchall():
                    bs = self._row2dict(row)
                    build_sets[row.id] = bs
            return build_sets

        return self.db.pool.do(thd)

    def getBuildsets(self, complete=None):
        def thd(conn):
            bs_tbl = self.db.model.buildsets
            q = bs_tbl.select()
            if complete is not None:
                if complete:
                    q = q.where(bs_tbl.c.complete != 0)
                else:
                    q = q.where((bs_tbl.c.complete == 0) |
                                (bs_tbl.c.complete == None))
            with conn_execute(conn, q) as res:
                return [ self._row2dict(row) for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def getRecentBuildsets(self, count, branch=None, repository=None,
                           complete=None):
        def thd(conn):
            bs_tbl = self.db.model.buildsets
            ss_tbl = self.db.model.sourcestamps
            j = sa.join(self.db.model.buildsets,
                               self.db.model.sourcestampsets)
            j = j.join(self.db.model.sourcestamps)
            q = sa.select(columns=[bs_tbl], from_obj=[j],
                                         distinct=True)
            q = q.order_by(sa.desc(bs_tbl.c.submitted_at))
            q = q.limit(count)

            if complete is not None:
                if complete:
                    q = q.where(bs_tbl.c.complete != 0)
                else:
                    q = q.where((bs_tbl.c.complete == 0) |
                                (bs_tbl.c.complete == None))
            if branch:
                q = q.where(ss_tbl.c.branch == branch)
            if repository:
                q = q.where(ss_tbl.c.repository == repository)
            with conn_execute(conn, q) as res:
                return list(reversed([ self._row2dict(row)
                                      for row in res.fetchall() ]))
        return self.db.pool.do(thd)

    def getBuildsetProperties(self, buildsetid):
        """
        Return the properties for a buildset, in the same format they were
        given to L{addBuildset}.

        Note that this method does not distinguish a nonexistent buildset from
        a buildset with no properties, and returns C{{}} in either case.

        @param buildsetid: buildset ID

        @returns: dictionary mapping property name to (value, source), via
        Deferred
        """
        def thd(conn):
            bsp_tbl = self.db.model.buildset_properties
            q = sa.select(
                [ bsp_tbl.c.property_name, bsp_tbl.c.property_value ],
                whereclause=(bsp_tbl.c.buildsetid == buildsetid))
            l = []
            with conn_execute(conn, q) as res:
                for row in res:
                    try:
                        properties = json.loads(row.property_value)
                        l.append((row.property_name,
                               tuple(properties)))
                    except ValueError:
                        pass
            return dict(l)
        return self.db.pool.do(thd)

    def getBuildsetsProperties(self, buildSetIds):
        def thd(conn):
            bsp_tbl = self.db.model.buildset_properties
            q = sa.select(
                [bsp_tbl.c.buildsetid, bsp_tbl.c.property_name, bsp_tbl.c.property_value],
                whereclause=(bsp_tbl.c.buildsetid.in_(buildSetIds)))
            buildSetsProperties = {}
            with conn_execute(conn, q) as res:
                for row in res:
                    try:
                        if row.buildsetid not in buildSetsProperties:
                            buildSetsProperties[row.buildsetid] = {}
                        properties = json.loads(row.property_value)
                        buildSetsProperties[row.buildsetid][row.property_name] = tuple(properties)
                    except ValueError:
                        pass

            return buildSetsProperties
        return self.db.pool.do(thd)

    def _row2dict(self, row):
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
        return BsDict(external_idstring=row.external_idstring,
                reason=row.reason, sourcestampsetid=row.sourcestampsetid,
                submitted_at=mkdt(row.submitted_at),
                complete=bool(row.complete),
                complete_at=mkdt(row.complete_at), results=row.results,
                bsid=row.id)
