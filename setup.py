#! /usr/bin/env python

from setuptools import setup, find_packages
import clin

requires = ['PyYAML',
            'requests',
            'jinja2',
            'paramiko',
            'scp']

setup_options = dict(
    name = 'clin',
    version = clin.__version__,
    scripts = ['bin/clin'],
    packages=find_packages('.', exclude=['tests*']),
    package_dir={'clin':'clin'},
    package_data={'clin': ['data/*.yml']},
    platforms = '*nix',
    install_requires=requires,
    )

setup(**setup_options)
