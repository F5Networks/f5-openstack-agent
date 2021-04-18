# -*- coding: utf-8 -*-

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

import eventlet
eventlet.monkey_patch(thread=True)


def get_engine(conf):

    engine_args = {
        "pool_recycle": conf.database.idle_timeout,
        "echo": False,
        "pool_size": conf.database.max_pool_size,
        "pool_timeout": conf.database.pool_timeout
    }

    return create_engine(conf.database.connection, **engine_args)


class Connection(object):

    __instance = None

    def __new__(cls, conf):
        if not isinstance(cls.__instance, cls):
            cls.__instance = super(Connection, cls).__new__(cls)
            cls.__instance.engine = get_engine(conf)
            cls.__instance.base = declarative_base(cls.__instance.engine)
        return cls.__instance


class Session(object):

    def __init__(self, conn):
        self.connection = conn
        self.engine = self.connection.engine
        self.scope_session = scoped_session(sessionmaker(
            bind=self.connection.engine))

    def __enter__(self):
        # print(self.engine.pool.status())
        session = self.scope_session()
        return session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.scope_session.remove()
