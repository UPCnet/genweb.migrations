from setuptools import setup, find_packages
import os

version = '1.0'

README = open("README.rst").read()
HISTORY = open(os.path.join("docs", "HISTORY.rst")).read()

setup(name='genweb.migrations',
      version=version,
      description="",
      long_description=README + "\n" + HISTORY,
      classifiers=[
          "Environment :: Web Environment",
          "Framework :: Plone",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2.7",
          "Topic :: Software Development :: Libraries :: Python Modules",
      ],
      keywords='genweb plone',
      author='UPCnet Plone Team',
      author_email='plone.team@upcnet.es',
      url='https://github.com/UPCnet/genweb.migrations.git',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['genweb', ],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'requests',
          'five.grok',
          'transmogrify.dexterity',
          'collective.jsonmigrator',
          'plone.api'
      ],
      entry_points="""
      # -*- Entry points: -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      )
