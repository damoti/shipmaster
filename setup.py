from setuptools import setup

setup(name='shipmaster',
      version='0.1',
      description='Continuous integration and deployment.',
      classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3',
      ],
      keywords='ci deployment testing',
      url='http://github.com/damoti/shipmaster',
      author='Lex Berezhny',
      author_email='lex@damoti.com',
      license='BSD',
      packages=['shipmaster'],
      install_requires=[
          'humanfriendly',
          'docker-map',
          'docker-compose',
          'ruamel.yaml'
      ],
      entry_points={
          'console_scripts': ['shipmaster=shipmaster.cli:main'],
      },
      include_package_data=True,
      zip_safe=False
)
