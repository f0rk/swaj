# Copyright 2021, Ryan P. Kelly.

from setuptools import setup


setup(
    name="swaj",
    version="0.5",
    description="AWS + CLI + MFA (pronounced like swage)",
    author="Ryan P. Kelly",
    author_email="ryan@ryankelly.us",
    url="https://github.com/f0rk/swaj",
    install_requires=[
        "botocore",
        "lockfile",
        "python-dateutil",
    ],
    tests_require=[
        "pytest",
    ],
    package_dir={"": "lib"},
    packages=["swaj"],
    scripts=["tools/swaj"],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Systems Administration",
    ],
)
