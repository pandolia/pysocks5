# -*- coding: utf-8 -*-

from setuptools import setup

version = '0.1'

setup(
    name = 'pysocks5',
    version = version,
    py_packages = ['pysocks5'],
    # entry_points = {
    #    'console_scripts': [
    #        'xxx = xxx:main',
    #    ]
    # },
    # install_requires = ['requests==2.7.0', 'certifi==2015.4.28', 'flask==0.11.1'],
    description = "pysocks5: A lightweight forward and backward socks5 proxy server written with python.",
    author = 'pandolia',
    author_email = 'pandolia@yeah.net',
    url = 'https://github.com/pandolia/pysocks5/',
    download_url = 'https://github.com/pandolia/pysocks5/archive/%s.tar.gz' % version,
    keywords = ['tcp', 'proxy', 'socks5', 'backward proxy'],
    classifiers = [],
)
