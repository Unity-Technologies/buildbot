import sqlalchemy as sa
from migrate.changeset import constraint


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    build_user_tbl = sa.Table("build_user", metadata,
        sa.Column('buildid', sa.Integer, nullable=False),
        sa.Column('userid', sa.Integer, nullable=True),
        sa.Column('finish_time', sa.Integer),
    )
    build_user_tbl.create()

    idx = sa.Index('build_user_buildid', build_user_tbl.c.buildid, build_user_tbl.c.userid)
    idx.create()

    users_tbl = sa.Table('users', metadata, autoload=True)
    builds_table = sa.Table('builds', metadata, autoload=True)

    cons = constraint.ForeignKeyConstraint([build_user_tbl.c.buildid], [builds_table.c.id])
    cons.create()

    cons = constraint.ForeignKeyConstraint([build_user_tbl.c.userid], [users_tbl.c.uid])
    cons.create()
