
import unittest
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy_softdelete import SoftDeleteSession, SoftDeletable

Base = declarative_base()

class User(Base, SoftDeletable):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

    def _delete(self):
        pass

class UserResource(Base):
    __tablename__ = 'user_resources'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    user_id = Column(ForeignKey(User.__tablename__ + '.id'), nullable=False)
    user = relationship(User, backref='resources')

class BadSoftDeletable(Base, SoftDeletable):
    __tablename__ = 'badsoftdeletables'
    id = Column(Integer, primary_key=True)


class TestSoftDelete(unittest.TestCase):

    def setUp(self):
        connectionstring = 'postgresql://myapp:dbpass@localhost:15432/test_softdelete'
        db_url = make_url(connectionstring)
        
        engine = create_engine(db_url, echo=True)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        SoftDeleteSession_ = sessionmaker(
                bind=engine,
                class_=SoftDeleteSession)
        self.sql_session = SoftDeleteSession_()

        self.user_id = 1
        self.user = User(id=self.user_id, name='Mattias')
        self.sql_session.add(self.user)
        self.sql_session.commit()

    def tearDown(self):
        self.sql_session.commit()

    def test_basic_soft_delete(self):
        self.sql_session.delete(self.user)
        self.sql_session.commit()
        self.sql_session.expire_all()
        query = self.sql_session.query(User).filter(User.id == self.user_id)
        self.assertEquals(query.count(), 0)
        # TODO get it with .execute()

    def test_non_nullable_foreign_key_raises_integrity_error(self):
        resource = UserResource(user_id=self.user.id)
        self.sql_session.add(resource)
        self.sql_session.commit()

        with self.assertRaises(IntegrityError):
            # Blows up because UserResource.user_id is non-nullable
            self.sql_session.delete(self.user)
            self.sql_session.commit()

        self.sql_session.expire_all()
        user = self.sql_session.query(User).get(self.user_id)
        # TODO: make sure not really deleted

    def test_nullable_foreign_key_is_updated(self):
        pass


    def test_cascading_deletes(self):
        # TODO (probably just mark as not implemented)
        pass

    def test_cannot_undelete(self):
        pass
        # TODO

    def test_raises_not_implemented(self):
        """
        SoftDeletable objects must implement delete()
        """
        bad = BadSoftDeletable(id=1)
        self.sql_session.add(bad)
        self.sql_session.commit()
        with self.assertRaises(NotImplementedError):
            self.sql_session.delete(bad)
