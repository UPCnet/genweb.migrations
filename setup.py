# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import os

version = '1.1'

README = open("README.rst").read()
HISTORY = open(os.path.join("docs", "HISTORY.rst")).read()

setup(name='genweb.jsonify',
      version=version,
      description="JSON export",
      long_description=README + "\n" + HISTORY,
      classifiers=[
          "Environment :: Web Environment",
          "Framework :: Plone",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2.6",
          "Programming Language :: Python :: 2.7",
          "Topic :: Software Development :: Libraries :: Python Modules",
      ],
      keywords='genweb json export',
      author='Victor Fernandez de Alba',
      author_email='sneridagh@gmail.com',
      url='https://github.com/UPCnet/genweb.jsonify',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['genweb'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
      ],
      extras_require={'test': ['plone.app.testing',
                               'plone.app.testing[robot]>=4.2.2',
                               'plone.app.robotframework[debug]',]},
      entry_points="""
      # -*- Entry points: -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      )
