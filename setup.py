#!/usr/bin/env python
import os
from setuptools import setup, find_packages


BASE = os.path.dirname(__file__)
README_PATH = os.path.join(BASE, 'README.rst')
CHANGES_PATH = os.path.join(BASE, 'CHANGES.rst')
long_description = '\n\n'.join((
    open(README_PATH).read(),
    open(CHANGES_PATH).read(),
))


setup(
    name='shipmaster',
    version='0.0.1',
    url='https://github.com/damoti/shipmaster',
    license='BSD',
    description='Continuous integration and deployment.',
    long_description=long_description,
    author='Lex Berezhny',
    author_email='lex@damoti.com',
    keywords='docker ci continuous integration build test deploy',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Testing',
    ],
    install_requires=[
        'humanfriendly',
        'docker-compose',
        'ruamel.yaml'
    ],
    packages=[
        'shipmaster.'+p for p in
        find_packages('shipmaster')
    ],
    entry_points={
        'console_scripts': ['shipmaster=shipmaster.cli:main'],
    },
)
