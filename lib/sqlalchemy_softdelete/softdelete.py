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
            self._check_deletable(instance, *args, **kwargs)

            # Good to go -- mark as deleted
            instance._deleted = True
            instance._delete()
        else:
            super(SoftDeleteSession, self).delete(instance, *args, **kwargs)

    def _check_deletable(self, instance, *args, **kwargs):
        # TODO/TBD: This might not actually be feasible...
        # If A has a foreign key to B, and you try to delete B without first
        # deleting A (or changing the key) things _should_ explode. However,
        # the actual DB constraint checker has no idea about this soft delete
        # business, so if A is also soft-deletable this will _still_ blow up
        # even if you first (soft) delete it. Options:
        # - Check foreign key constraints "manually", by way of some magic
        #   "SELECT ALL ROWS IN ALL TABLES THAT REFERENCE instance" query.
        #   I don't even know if that's a thing. Ugh.
        # - Ditch the whole "try a real delete and roll back" approach entirely.
        #   Ugh. Instead model objects using this would need to add all such
        #   checks to the SoftDeletable._delete method.

        # Check that instance is deletable in the traditional sense
        local_transaction = False
        if not self.transaction:
            self.begin()
            local_transaction = True
        self.begin_nested() # Establishes a savepoint
        try:
            self._super.delete(instance, *args, **kwargs)
            # flush() will be rolled back -- we just want to see if
            # anything explodes
            self.flush()
        except IntegrityError as e:
            self.rollback() # Rolls back to savepoint
            if local_transaction:
                self.rollback()
            raise e
        self.rollback() # Rolls back to savepoint
        if local_transaction:
            self.rollback()

class SoftDeleteQuery(Query):

    def __iter__(self):
        return Query.__iter__(self.check_deleted())

    def from_self(self, *ent):
        # override from_self() to automatically apply
        # the criterion too. This works with count() and
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
        """
        Override this method for any necessary domain-specific side effects.
        """
        pass
