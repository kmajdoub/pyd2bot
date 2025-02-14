from setuptools import find_packages, setup

setup(
    # Application name:
    name="pyd2bot",
    # Version number (initial):
    version=open("./VERSION").read(),
    # Application author details:
    author="majdoub khalid",
    author_email="majdoub.khalid@gmail.com",
    # Packages
    packages=find_packages(),
    # Include additional files into the package
    include_package_data=True,
    # Details
    url="https://github.com/hadamrd/pyd2bot",
    #
    # license="LICENSE.txt",
    description="Python bot that uses pydofus2 as a background client.",
    long_description=open("README.md").read(),
    # Dependent packages (distributions)
    install_requires=open("./requirements.txt").readlines(),
    classifiers=[
        "Programming Language :: Python :: 3.9.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Windows",
    ],
    python_requires="<=3.9.13",
)
