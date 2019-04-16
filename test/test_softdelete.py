import unittest
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy_softdelete import SoftDeleteSession, SoftDeletable

Base = declarative_base()


class User(Base, SoftDeletable):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class UserResource(Base):
    __tablename__ = 'user_resources'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    _user_id = Column(ForeignKey(User.__tablename__ + '.id'), nullable=False)
    user = relationship(User, backref='resources')


class UserResourceWithNullableForeignKey(Base):
    __tablename__ = 'nullable_user_resources'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    _user_id = Column(ForeignKey(User.__tablename__ + '.id'), nullable=True)
    user = relationship(User, backref='nullable_resources')


class SoftDeletableUserResource(Base, SoftDeletable):
    __tablename__ = 'softdeletable_user_resources'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    _user_id = Column(ForeignKey(User.__tablename__ + '.id'), nullable=False)
    user = relationship(User, backref='softdeletable_resources')


class CascadingDeleteResource(Base):
    __tablename__ = 'cascading_delete_resources'
    id = Column(Integer, primary_key=True)
    value = Column(String)
    _user_id = Column(ForeignKey(User.__tablename__ + '.id'))
    user = relationship(User, backref='cascading_delete_resources', cascade='delete')


class BadSoftDeletable(Base, SoftDeletable):
    __tablename__ = 'badsoftdeletables'
    id = Column(Integer, primary_key=True)


class TestSoftDelete(unittest.TestCase):

    def setUp(self):
        connectionstring = 'postgresql://softdelete:softdelete@localhost:5432/test_softdelete'
        db_url = make_url(connectionstring)

        engine = create_engine(db_url, echo=True)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        SoftDeleteSession_ = sessionmaker(
                bind=engine,
                class_=SoftDeleteSession)
        self.softdelete_session = SoftDeleteSession_()

        RegularSession_ = sessionmaker(
                bind=engine,
                class_=Session)
        self.regular_session = RegularSession_()

        self.user_id = 1
        self.user = User(id=self.user_id, name='Mattias')
        self.softdelete_session.add(self.user)
        self.softdelete_session.commit()

    def tearDown(self):
        self.softdelete_session.commit()

    def test_basic_soft_delete(self):
        self.softdelete_session.delete(self.user)
        self.softdelete_session.commit()
        self.softdelete_session.expire_all()

        # ORM query behaves as if the row is deleted
        query = self.softdelete_session.query(User).filter(User.id == self.user_id)
        self.assertEquals(query.count(), 0)

        # User is still in the database and can be gotten with raw SQL
        query_text = 'SELECT * FROM users WHERE id = {0};'.format(self.user_id)
        result = self.softdelete_session.execute(query_text)
        result = result.first()
        self.assertTrue(result['_deleted'])

    def test_non_nullable_foreign_key_raises_integrity_error(self):
        resource = UserResource(user=self.user)
        self.softdelete_session.add(resource)
        self.softdelete_session.commit()
        self.assertEqual(resource.user, self.user)
        resource_id = resource.id

        with self.assertRaises(IntegrityError) as err:
            # Blows up because UserResource.user_id is non-nullable
            self.softdelete_session.delete(self.user)
            self.softdelete_session.commit()
        softdelete_error = str(err.exception)

        # Transaction was safely rolled back, and the user and resource
        # still exists
        self.softdelete_session.expire_all()
        user = self.softdelete_session.query(User).get(self.user_id)
        self.assertEqual(user.resources[0].id, resource_id)

        self.softdelete_session.close()
        self.regular_session.add(self.user)
        # Check that we get the exact same error message as with a regular SQLAlchemy session
        with self.assertRaises(IntegrityError) as err:
            self.regular_session.delete(self.user)
            self.regular_session.commit()
        regular_error = str(err.exception)
        self.assertEqual(regular_error, softdelete_error)

    def test_nullable_foreign_key(self):
        resource = UserResourceWithNullableForeignKey(user=self.user)
        self.softdelete_session.add(resource)
        self.softdelete_session.commit()
        self.assertEqual(resource.user, self.user)

        self.softdelete_session.delete(self.user)
        self.softdelete_session.commit()

        # User object is gone from the resource as far as the ORM is concerned
        self.assertIsNone(resource.user)

        # You also can't get it "accidentally" with join queries:
        with self.assertRaises(NoResultFound):
            self.softdelete_session.query(
                    User,
                    UserResourceWithNullableForeignKey
                ).filter(User.id == UserResourceWithNullableForeignKey._user_id).one()

        # However, the underlying foreign key is not updated, preserving the
        # underlying relationship
        self.assertEqual(self.user_id, resource._user_id)

    def test_softdeletable_relations(self):
        resource = SoftDeletableUserResource(user=self.user)
        self.softdelete_session.add(resource)
        self.softdelete_session.commit()
        self.assertEqual(resource.user, self.user)

        with self.assertRaises(IntegrityError):
            self.softdelete_session.delete(self.user)
            self.softdelete_session.commit()

    def test_basic_bulk_delete(self):
        self.softdelete_session.query(User).delete()
        self.softdelete_session.commit()
        users = self.softdelete_session.query(User).all()
        self.assertEquals(len(users), 0)
        # Check that they're still there and marked deleted
        query_text = 'SELECT * FROM users'
        result = self.softdelete_session.execute(query_text)
        result = result.first()
        self.assertTrue(result['_deleted'])

    def test_bulk_delete_of_non_soft_deletable(self):
        # TODO
        pass

    def test_aggregate_functions(self):
        self.softdelete_session.delete(self.user)
        self.softdelete_session.commit()
        self.assertEqual(self.softdelete_session.query(User).count(), 0)

    @unittest.skip("Not supported")
    def test_cascading_deletes(self):
        cascading_resource = CascadingDeleteResource(user_id=self.user.id)
        self.softdelete_session.add(cascading_resource)
        self.softdelete_session.commit()
        self.softdelete_session.delete(cascading_resource)
        self.softdelete_session.commit()
        # TODO: This ends up fully deleting the user. Figure out how to
        # either mark it as deleted, or raise a NotImplementedError
