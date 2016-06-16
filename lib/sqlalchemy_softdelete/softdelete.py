from sqlalchemy import Column, Boolean
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.session import Session

class SoftDeleteSession(Session):

    def __init__(self, *args, **kwargs):
        self._super = super(SoftDeleteSession, self)
        self._super.__init__(query_cls=SoftDeleteQuery, *args, **kwargs)
    
    def query(self, *args, **kwargs):
        # TODO: Make exclude_deleted really exclude deleted
        #kwargs.setdefault('exclude_deleted', True)
        return super(SoftDeleteSession, self).query(*args, **kwargs)

    def delete(self, instance, *args, **kwargs):
        if isinstance(instance, SoftDeletable):
            # Check that instance is deletable in the traditional sense
            self.begin_nested() # Establishes a savepoint
            try:
                self._super.delete(instance, *args, **kwargs)
                self.flush()
            except IntegrityError as e:
                self.rollback() # Rolls back to savepoint
                raise e
            self.rollback() # Rolls back to savepoint

            # Good to go -- mark as deleted
            instance._deleted = True
            instance._delete()
        else:
            super(SoftDeleteSession, self).delete(instance, *args, **kwargs)

class SoftDeleteQuery(Query):

    def __iter__(self):
        try:
            Query.__iter__(self.check_deleted())
        except Exception as e:
            import dbg;dbg.dbg()
        return Query.__iter__(self.check_deleted())

    def from_self(self, *ent):
        # override from_self() to automatically apply
        # the criterion too.   this works with count() and
        # others.
        return Query.from_self(self.check_deleted(), *ent)

    def check_deleted(self):
        mapper_zero = self._mapper_zero()
        if mapper_zero is not None:
            if issubclass(mapper_zero.class_, SoftDeletable):
                filt = mapper_zero.class_._deleted == False
                #return self.enable_assertions(False).filter(filt)
                return self.filter(filt)
        return self

class SoftDeletable(object):

    _deleted = Column(Boolean, default=False, nullable=False)

    def _delete(self):
        raise NotImplementedError()
