from setuptools import setup, find_packages

setup(
    name='gmusic-sync',
    version='0.1.0',
    description='Beets plugin for syncing music to Google Play Music',
    url='https://github.com/brannon/gmusic-sync',
    author='Brannon Jones',
    packages=['beetsplug'],
    install_requires=['arrow','gmusicapi'],
)