#! /usr/bin/env python

from setuptools import setup, find_packages
import clin

setup_options = dict(
    name = 'clin',
    version = clin.__version__,
    scripts = ['bin/clin'],
    packages=find_packages('.', exclude=['tests*']),
    package_dir={'clin':'clin'},
    package_data={'clin': ['data/*.yml']},
    platforms = '*nix',
    )

setup(**setup_options)
