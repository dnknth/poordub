from setuptools import setup, find_packages


with open( "requirements.txt", "r") as fh:
    requirements = fh.read().splitlines()

setup(
    name="poordub",
    version="0.1.0",
    description="Poor man's PyDub",
    license="MIT",
    author="dnknth",
    url="https://github.com/dnknth/poordub.git",
    py_modules=[ "poordub" ],
    install_requires=requirements,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries'
    ],
)
