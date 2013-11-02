#! /usr/bin/env python

from setuptools import setup, find_packages

PACKAGE = 'clin'
NAME = 'clin'
KEYWORDS = ('cloud', 'aws', 'openstack')
VERSION = __import__(PACKAGE).__version__
DESCRIPTION = 'deploy service on cloud platform'
LICENSE = 'GPL'
URL = ''
AUTHOR = 'yupeng'
AUTHOR_EMAIL = 'yupeng0921@gmail.com'

setup(
    name = NAME,
    version = VERSION,
    keywords = KEYWORDS,
    description = DESCRIPTION,
    license = LICENSE,

    url = URL,
    author = AUTHOR,
    author_email = AUTHOR_EMAIL,

    scripts = ['bin/clin'],
    packages = find_packages(),
    include_package_data = True,
    platforms = '*nix',
    )
