# SQLAlchemy Softdelete

This library supports transparent soft/logical deletes using the SQLAlchemy ORM
model. Records are marked as deleted by the familiar `delete()` method, and are
thereafter invisible to the ORM, while the underlying database rows are retained
for auditing or other purposes.

## Basic Usage

To enable soft deletes for a mapped table, simply inherit `SoftDeletable`:

```
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_softdelete import SoftDeletable

Base = declarative_base()

class User(Base, SoftDeletable):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
```

This requires a migration for existing tables to create a `_deleted` boolean
column.

Next, your session object must be created using a `SoftDeleteSession`, e.g.:

```
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_softdelete import SoftDeleteSession

engine = create_engine('postgresql://softdelete:softdelete@localhost:5432/test_softdelete')

SoftDeleteSession_ = sessionmaker(
        bind=engine,
        class_=SoftDeleteSession)
session = SoftDeleteSession_()
```

Add some data:

```
user = User(id=10, name='Mattias')
session.add(user)
session.commit()
```

You can delete it as normal, and it will be gone as far as the ORM is concerned:

```
session.delete(user)
session.commit()
assert session.query(User).filter_by(id=10).one_or_none() == None
```

But the underlying data is still present:

```
assert session.execute("SELECT COUNT(*) FROM users WHERE id=10").first()[0] == 1
```

## Requirements and limitations

Target database must support SAVEPOINTs.

Cascading deletes are not supported.

## Running tests

Tests assume that a PostgreSQL instance is available on `localhost` port 5432, with a
`softdelete` user and `test_softdelete` database:

```
CREATE USER softdelete WITH PASSWORD 'softdelete';
CREATE DATABASE test_softdelete;
```
