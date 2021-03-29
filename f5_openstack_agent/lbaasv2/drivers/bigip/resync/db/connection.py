# -*- coding: utf-8 -*-

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


class Connection(object):

    __instance = None

    def __new__(cls, conn):
        if not isinstance(cls.__instance, cls):
            cls.__instance = super(Connection, cls).__new__(cls)
            cls.__instance.engine = create_engine(conn, echo=True)
            cls.__instance.base = declarative_base(cls.__instance.engine)
            cls.__instance.sessionmaker = sessionmaker(bind=cls.__instance.engine)
        return cls.__instance

    @property
    def session(self):
        # return a new session everytime
        return self.sessionmaker()

if __name__ == "__main__":

    for i in range(10):
        a = Connection('mysql+pymysql://root:stackdb@127.0.0.1/neutron?charset=utf8')
        s = a.session
        print id(a)
        print id(a.engine)
        print id(s)
        print
