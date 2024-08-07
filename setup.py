#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open('VERSION.txt', 'r') as v:
    version = v.read().strip()

with open('README.rst', 'r') as r:
    readme = r.read()

download_url = (
    'https://github.com/alirezaazadi/django-chunked-upload/%s'
)

setup(
    name='django-chunked-upload',
    packages=['chunked_upload', 'chunked_upload.migrations', 'chunked_upload.management'],
    version=version,
    description=('Upload large files to Django in multiple chunks through RESTful API,'
                 ' with the ability to resume if the upload is interrupted.'),
    long_description=readme,
    install_requires=[
        'djangorestframework==3.14.0',
    ],
    author='Alireza Azadi',
    author_email='Alireza_Azadi@Hotmail.com',
    url='https://github.com/alirezaazadi/django-chunked-upload',
    download_url=download_url % version,
    license='MIT-Zero',
)
