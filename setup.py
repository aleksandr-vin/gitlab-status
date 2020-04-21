from setuptools import setup

setup(
    name='pipeline-stats',
    version='0.0',
    install_requires=[
        'python-gitlab>=1.10.0'
    ],
    packages=['pipeline_stats'],
    entry_points={
        'console_scripts': [
            'releasekeeper = releasekeeper.releasekeeper:main',
            'releasekeeper-setup = releasekeeper.setupenv:main',
        ],
    }
)
