import setuptools

with open('README.md', 'r') as fh:
  long_description = fh.read()

setuptools.setup(
  name='pytranscoder-ffmpeg',
  version='1.0.0',
  author='Marshall L Smith Jr',
  author_email='marshallsmithjr@gmail.com',
  description='A ffmpeg wrapper to better manage transcode operations',
  long_description = long_description,
  long_description_content_type = 'text/markdown',
  url='https://github.com/mlsmithjr/transcoder',
  packages=setuptools.find_packages(),
  classifiers=[
    'Programming Lanaguge :: ython :: 3',
    'License :: OSI Approved :: GNU License',
    'Operating System :: OS Independent',
  ],
)

