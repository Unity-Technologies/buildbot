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

import sqlalchemy as sa
from sqlalchemy.sql.expression import and_

from buildbot.db import base

class UsDict(dict):
    pass

class UsersConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def findUserByAttr(self, identifier, attr_type, attr_data, _race_hook=None, fullname=None, mail=None):
        def thd(conn, no_recurse=False):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            self.check_length(tbl.c.identifier, identifier)
            self.check_length(tbl_info.c.attr_type, attr_type)
            self.check_length(tbl_info.c.attr_data, attr_data)
            if fullname:
                self.check_length(tbl.c.fullname, fullname)
            if mail:
                self.check_length(tbl.c.mail, mail)

            # try to find the user from the attributes
            info_query = sa.select([tbl_info.c.uid],
                                   whereclause=and_(tbl_info.c.attr_type == attr_type,
                                                    tbl_info.c.attr_data == attr_data))
            info_data = conn.execute(info_query).fetchall()

            # try to find the user from the users table
            user_query = sa.select([tbl.c.uid, tbl.c.fullname, tbl.c.mail],
                                   whereclause=and_(tbl.c.identifier == identifier))
            user_data = conn.execute(user_query).fetchall()

            # Check if we need to update the name or the mail
            if user_data:
                old_name = user_data[0].fullname
                old_mail = user_data[0].mail
                update_dict = {}
                if fullname and (old_name is None or old_name.encode('utf-8') != fullname):
                    update_dict['fullname'] = fullname.decode('utf-8')
                if mail and (old_mail is None or old_mail.encode('utf-8') != mail):
                    update_dict['mail'] = mail.decode('utf-8')

                if update_dict:
                    transaction = conn.begin()
                    try:
                        conn.execute(tbl.update(whereclause=(tbl.c.uid == user_data[0].uid)),
                                     update_dict)
                    except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                        transaction.rollback()
                        raise
                    transaction.commit()

            # If we have the attributes
            if info_data:
                return info_data[0].uid

            # same user may exists in other repository example hg/git
            # we insert the attributes
            if user_data:
                transaction = conn.begin()
                try:
                    old_data = conn.execute(
                        sa.select([tbl_info.c.attr_data],
                                  whereclause=and_(tbl_info.c.attr_type == attr_type,
                                                   tbl_info.c.uid == user_data[0].uid))).fetchone()

                    # We need to check if the attr_data is inconsistent. Then we update instead.
                    if old_data and old_data.attr_data != attr_data:
                        conn.execute(tbl_info.update(
                            whereclause=and_(tbl_info.c.uid == user_data[0].uid,
                                             tbl_info.c.attr_type == attr_type)),
                                     dict(attr_data=attr_data))

                    else:
                        conn.execute(tbl_info.insert(),
                                     dict(uid=user_data[0].uid, attr_type=attr_type,
                                          attr_data=attr_data))
                    transaction.commit()
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                    transaction.rollback()
                    raise

                return user_data[0].uid

            _race_hook and _race_hook(conn)

            # try to do both of these inserts in a transaction, so that both
            # the new user and the corresponding attributes appear at the same
            # time from the perspective of other masters.
            transaction = conn.begin()
            try:
                r = conn.execute(tbl.insert(), dict(identifier=identifier,
                                                    fullname=fullname, mail=mail))
                uid = r.inserted_primary_key[0]

                conn.execute(tbl_info.insert(),
                             dict(uid=uid, attr_type=attr_type,
                                  attr_data=attr_data))

                transaction.commit()
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                transaction.rollback()

                # try it all over again, in case there was an overlapping,
                # identical call to findUserByAttr, but only retry once.
                if no_recurse:
                    raise
                return thd(conn, no_recurse=True)

            return uid
        d = self.db.pool.do(thd)
        return d

    @base.cached("usdicts")
    def getUser(self, uid):
        def thd(conn):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            q = tbl.select(whereclause=(tbl.c.uid == uid))
            users_row = conn.execute(q).fetchone()

            if not users_row:
                return None

            # make UsDict to return
            usdict = UsDict()

            # gather all attr_type and attr_data entries from users_info table
            q = tbl_info.select(whereclause=(tbl_info.c.uid == uid))
            rows = conn.execute(q).fetchall()
            for row in rows:
                usdict[row.attr_type] = row.attr_data

            # add the users_row data *after* the attributes in case attr_type
            # matches one of these keys.
            usdict['uid'] = users_row.uid
            usdict['identifier'] = users_row.identifier
            usdict['bb_username'] = users_row.bb_username
            usdict['bb_password'] = users_row.bb_password

            return usdict
        d = self.db.pool.do(thd)
        return d

    def getUserByUsername(self, username):
        def thd(conn):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            q = tbl.select(whereclause=(tbl.c.bb_username == username))
            users_row = conn.execute(q).fetchone()

            if not users_row:
                return None

            # make UsDict to return
            usdict = UsDict()

            # gather all attr_type and attr_data entries from users_info table
            q = tbl_info.select(whereclause=(tbl_info.c.uid == users_row.uid))
            rows = conn.execute(q).fetchall()
            for row in rows:
                usdict[row.attr_type] = row.attr_data

            # add the users_row data *after* the attributes in case attr_type
            # matches one of these keys.
            usdict['uid'] = users_row.uid
            usdict['identifier'] = users_row.identifier
            usdict['bb_username'] = users_row.bb_username
            usdict['bb_password'] = users_row.bb_password

            return usdict
        d = self.db.pool.do(thd)
        return d

    def getIdentifierByMail(self, mail, author):
        def thd(conn):
            tbl = self.db.model.users

            q = tbl.select(whereclause=(tbl.c.mail == mail))
            users_row = conn.execute(q).fetchone()

            if not users_row:
                return author

            return users_row.identifier
        d = self.db.pool.do(thd)
        return d

    def getUsers(self):
        def thd(conn):
            tbl = self.db.model.users
            rows = conn.execute(tbl.select()).fetchall()

            dicts = []
            if rows:
                for row in rows:
                    ud = dict(uid=row.uid, identifier=row.identifier)
                    dicts.append(ud)
            return dicts
        d = self.db.pool.do(thd)
        return d

    def get_all_user_props(self, uid):
        def thd(conn):
            tbl = self.db.model.user_props
            q = tbl.select(whereclause=(tbl.c.uid == uid))
            rows = conn.execute(q).fetchall()

            output = {}
            if rows:
                for row in rows:
                    output[row.prop_type] = row.prop_data
            return output

        d = self.db.pool.do(thd)
        return d

    def get_user_prop(self, uid, attr):
        def thd(conn):
            tbl = self.db.model.user_props
            q = tbl.select(whereclause=(tbl.c.uid == uid) & (tbl.c.prop_type == attr))
            row = conn.execute(q).fetchone()

            if row is not None:
                return row.prop_data
            else:
                return None

        d = self.db.pool.do(thd)
        return d

    def set_user_prop(self, uid, prop_type, prop_data, _race_hook=None):
        def thd(conn):
            tbl_props = self.db.model.user_props
            transaction = conn.begin()
            assert prop_data is not None

            self.check_length(tbl_props.c.prop_type, prop_type)
            self.check_length(tbl_props.c.prop_data, prop_data)

            # first update, then insert
            q = tbl_props.update(whereclause=(tbl_props.c.uid == uid) & (tbl_props.c.prop_type == prop_type))
            res = conn.execute(q, prop_data=prop_data)
            if res.rowcount == 0:
                _race_hook and _race_hook(conn)

                # the update hit 0 rows, so try inserting a new one
                try:
                    q = tbl_props.insert()
                    res = conn.execute(q,
                            uid=uid,
                            prop_type=prop_type,
                            prop_data=prop_data)
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError) as e:
                    # someone else beat us to the punch inserting this row;
                    # let them win.
                    print e
                    transaction.rollback()
                    return

            transaction.commit()

        d = self.db.pool.do(thd)
        return d

    def updateUser(self, uid=None, identifier=None, bb_username=None,
                   bb_password=None, attr_type=None, attr_data=None,
                   _race_hook=None):
        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info
            update_dict = {}

            # first, add the identifier is it exists
            if identifier is not None:
                self.check_length(tbl.c.identifier, identifier)
                update_dict['identifier'] = identifier

            # then, add the creds if they exist
            if bb_username is not None:
                assert bb_password is not None
                self.check_length(tbl.c.bb_username, bb_username)
                self.check_length(tbl.c.bb_password, bb_password)
                update_dict['bb_username'] = bb_username
                update_dict['bb_password'] = bb_password

            # update the users table if it needs to be updated
            if update_dict:
                q = tbl.update(whereclause=(tbl.c.uid == uid))
                res = conn.execute(q, update_dict)

            # then, update the attributes, carefully handling the potential
            # update-or-insert race condition.
            if attr_type is not None:
                assert attr_data is not None

                self.check_length(tbl_info.c.attr_type, attr_type)
                self.check_length(tbl_info.c.attr_data, attr_data)

                # first update, then insert
                q = tbl_info.update(
                        whereclause=(tbl_info.c.uid == uid)
                                    & (tbl_info.c.attr_type == attr_type))
                res = conn.execute(q, attr_data=attr_data)
                if res.rowcount == 0:
                    _race_hook and _race_hook(conn)

                    # the update hit 0 rows, so try inserting a new one
                    try:
                        q = tbl_info.insert()
                        res = conn.execute(q,
                                uid=uid,
                                attr_type=attr_type,
                                attr_data=attr_data)
                    except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                        # someone else beat us to the punch inserting this row;
                        # let them win.
                        transaction.rollback()
                        return

            transaction.commit()
        d = self.db.pool.do(thd)
        return d

    def removeUser(self, uid):
        def thd(conn):
            # delete from dependent tables first, followed by 'users'
            for tbl in [
                    self.db.model.change_users,
                    self.db.model.users_info,
                    self.db.model.users,
                    ]:
                conn.execute(tbl.delete(whereclause=(tbl.c.uid==uid)))
        d = self.db.pool.do(thd)
        return d

    def identifierToUid(self, identifier):
        def thd(conn):
            tbl = self.db.model.users

            q = tbl.select(whereclause=(tbl.c.identifier == identifier))
            row = conn.execute(q).fetchone()
            if not row:
                return None

            return row.uid
        d = self.db.pool.do(thd)
        return d
