import setuptools
import sys
import re
import os

if sys.version_info < (3, 6):
    print('pytranscoder requires at least Python 3.6 to run.')
    sys.exit(1)

with open(os.path.join('pytranscoder', '__init__.py'), encoding='utf-8') as f:
    version = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M).group(1)

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='pytranscoder-ffmpeg',
    version=version,
    python_requires='>=3.6',
    author='Marshall L Smith Jr',
    author_email='marshallsmithjr@gmail.com',
    description='A ffmpeg wrapper to better manage transcode operations',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    extras_require={'with_plexapi': ['plexapi>=3.1.0']},
    url='https://github.com/mlsmithjr/transcoder',
    data_files=[('share/doc/pytranscoder', ['README.md', 'transcode.yml'])],
    packages=['pytranscoder'],
    entry_points={"console_scripts": ["pytranscoder=pytranscoder.transcode:main"]},
    classifiers=[
      'Programming Language :: Python :: 3',
      'Environment :: Console',
      'Topic :: Multimedia :: Video :: Conversion',
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Natural Language :: English',
      'Operating System :: POSIX :: Linux',
    ],
)

