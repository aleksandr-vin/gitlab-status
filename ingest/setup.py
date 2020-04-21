from setuptools import setup

with open('requirements.txt') as f:
    requirements = f.readlines()
    requirements = [x.strip() for x in requirements] 

setup(
    name='ingest',
    version='0.0',
    install_requires=requirements,
    packages=['ingest'],
    entry_points={
        'console_scripts': [
            'ingest = ingest.ingest:main'
        ],
    }
)
