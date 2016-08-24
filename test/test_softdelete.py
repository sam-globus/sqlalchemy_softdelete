
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

class CascadingDeleteResource(Base):
    __tablename__ = 'cascading_delete_resources'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    user_id = Column(ForeignKey(User.__tablename__ + '.id'))
    user = relationship(User, backref='cascading_delete_resources', cascade='delete')

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

        # ORM query behaves as if the row is deleted
        query = self.sql_session.query(User).filter(User.id == self.user_id)
        self.assertEquals(query.count(), 0)

        # User is still in the database and can be gotten with raw SQL
        query_text = 'SELECT * FROM users WHERE id = {0};'.format(self.user_id)
        result = self.sql_session.execute(query_text)
        result = result.first()
        self.assertTrue(result['_deleted'])

    def test_non_nullable_foreign_key_raises_integrity_error(self):
        resource = UserResource(user_id=self.user.id)
        self.sql_session.add(resource)
        self.sql_session.commit()
        resource_id = resource.id

        with self.assertRaises(IntegrityError):
            # Blows up because UserResource.user_id is non-nullable
            self.sql_session.delete(self.user)
            self.sql_session.commit()

        # Transaction was safely rolled back, and the user and resource
        # still exists
        self.sql_session.expire_all()
        user = self.sql_session.query(User).get(self.user_id)
        self.assertEqual(user.resources[0].id, resource_id)

    def test_nullable_foreign_key_is_updated(self):
        # TODO
        pass

    def test_instance__check_deleted(self):
        # TODO: If a soft-deletable is referenced by another soft-deletable
        # it must be handled by overriding _check_deleted.
        pass

    def test_bulk_delete(self):
        self.sql_session.query(User).delete()
        self.sql_session.commit()
        users = self.sql_session.query(User).all()
        self.assertEquals(len(users), 0)
        # Check that they're still there and marked deleted
        query_text = 'SELECT * FROM users'
        result = self.sql_session.execute(query_text)
        result = result.first()
        self.assertTrue(result['_deleted'])
        # TODO: Implement/test that _check_deletable and _delete calls are called
        # so that constraints are respected

    def test_bulk_delete_of_non_soft_deletable(self):
        # TODO
        pass

    @unittest.skip("Not supported")
    def test_cascading_deletes(self):
        cascading_resource = CascadingDeleteResource(user_id=self.user.id)
        self.sql_session.add(cascading_resource)
        self.sql_session.commit()
        self.sql_session.delete(cascading_resource)
        self.sql_session.commit()
        # TODO: This ends up fully deleting the user. Figure out how to
        # either mark it as deleted, or raise a NotImplementedError
