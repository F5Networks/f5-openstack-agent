# -*- coding: utf-8 -*-

from f5_openstack_agent.lbaasv2.drivers.bigip.resync.db import connection
from oslo_config import cfg
from oslo_db import options
import sys

from sqlalchemy import Table, Column, String, ForeignKey
from sqlalchemy.orm import relationship

conf = cfg.ConfigOpts()
# conf = cfg.CONF
conf.register_opts(options.database_opts, group='database')
conf(sys.argv[1:])

con = connection.Connection(conf.database.connection)
Base = con.base
metadata = Base.metadata


class Loadbalancer(Base):
    __tablename__ = 'lbaas_loadbalancers'
    __table_args__ = {'autoload':True}


class Listener(Base):
    __tablename__ = 'lbaas_listeners'
    __table_args__ = {'autoload':True}

    loadbalancer_id = Column("loadbalancer_id")

class Pool(Base):
    __tablename__ = 'lbaas_pools'
    __table_args__ = {'autoload':True, 'extend_existing': True}

    loadbalancer_id = Column("loadbalancer_id")
    healthmonitor_id = Column(String, ForeignKey('lbaas_healthmonitors.id'))

    members = relationship("Member")
    healthmonitor = relationship("Monitor", uselist=False)


class Monitor(Base):
    __tablename__ = 'lbaas_healthmonitors'
    __table_args__ = {'autoload':True}


class Member(Base):
    __tablename__ = 'lbaas_members'
    __table_args__ = {'autoload':True}

    pool_id = Column(String, ForeignKey('lbaas_pools.id'))
