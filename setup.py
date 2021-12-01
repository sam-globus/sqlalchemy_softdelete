#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="sqlalchemy_softdelete",
    version="1.1",
    url="http://github.com/mattias-lidman/sqlalchemy_softdelete",
    license="BSD",
    description="Soft deletes in SQLAlchemy",
    author="Mattias Lidman",
    packages=find_packages("lib"),
    package_dir={"": "lib"},
    install_requires=["setuptools"],
)
