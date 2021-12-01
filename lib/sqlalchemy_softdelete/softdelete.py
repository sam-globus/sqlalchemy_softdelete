from sqlalchemy import Column, Boolean
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import persistence
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.session import Session


class SoftDeleteSession(Session):

    def __init__(self, *args, **kwargs):
        self._super = super(SoftDeleteSession, self)
        kwargs['enable_baked_queries'] = False
        self._super.__init__(query_cls=SoftDeleteQuery, *args, **kwargs)
        # Flag allowing you to disable the soft delete query.
        self.disable_soft_delete_query = False

    def query(self, *entities, **kwargs):
        return super(SoftDeleteSession, self).query(*entities, **kwargs) \
            if not self.disable_soft_delete_query else Query(entities, self, **kwargs)

    def delete(self, instance, *args, **kwargs):
        if isinstance(instance, SoftDeletable):
            instance._check_deletable(self, *args, **kwargs)

            # Good to go -- mark as deleted
            instance._deleted = True
            instance._delete()
        else:
            super(SoftDeleteSession, self).delete(instance, *args, **kwargs)


class SoftDeleteQuery(Query):

    def __init__(self, entities, session=None):
        self.entities = entities
        super(SoftDeleteQuery, self).__init__(entities, session)

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
                filt = mapper_zero.class_._deleted == False # noqa
                return self.filter(filt)
        return self

    def delete(self, synchronize_session='evaluate'):
        """
        Perform a bulk-delete.
        """
        if len(self.entities) != 1:
            raise NotImplementedError("Bulk delete only supported on single table")
        if issubclass(self.entities[0], SoftDeletable):
            values = {'_deleted' : True}
            update_args = {}
            update_op = persistence.BulkUpdate.factory(
                    self, synchronize_session, values, update_args)
            # TODO: How to _check_deletable here?
            #instance._check_deletable(self, *args, **kwargs)

            # Good to go -- mark as deleted
            update_op.exec_()
            # TODO: How to run _deleted on these?
        else:
            # TODO: Test that this works
            super(SoftDeleteQuery, self).delete(synchronize_session=synchronize_session)


class SoftDeletable(object):

    _deleted = Column(Boolean, default=False, nullable=False)

    def _delete(self):
        """
        Override this method for any necessary domain-specific side effects.
        """
        pass

    def _check_deletable(self, sql_session, *args, **kwargs):
        """
        This method needs to verify that all consistency requirements for
        deletion are met.

        Normally, this is done by simply attempting to delete the instance in
        the traditional sense, rolling back the result and re-raising any
        resulting exceptions.

        It may sometimes be necessary to override this method for domain-specific
        validation.
        """
        local_transaction = False
        if not sql_session.transaction:
            sql_session.begin()
            local_transaction = True
        sql_session.begin_nested() # Establishes a savepoint
        try:
            sql_session._super.delete(self, *args, **kwargs)
            # flush() will be rolled back -- we just want to see if
            # anything explodes
            sql_session.flush()
        except IntegrityError as e:
            sql_session.rollback() # Rolls back to savepoint
            if local_transaction:
                sql_session.rollback()
            raise e
        sql_session.rollback() # Rolls back to savepoint
        if local_transaction:
            sql_session.rollback()


class SoftDeleteIntegrityError(IntegrityError):

    def __init__(self, message):
        self.detail = []
        self.message = message

    def __str__(self):
        return self.message
