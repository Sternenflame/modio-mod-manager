from setuptools import setup, find_packages

setup(
    name="modio-mod-manager",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'mod.io==0.5.0',
        'pyYAML==6.0',
        'progress==1.6',
        'python-dotenv==1.0.0',
        'requests==2.31.0',
    ],
) 