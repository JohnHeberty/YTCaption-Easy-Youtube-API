"""
Setup configuration for YTCaption Common Library
"""
from setuptools import setup, find_packages

setup(
    name="ytcaption-common",
    version="1.0.0",
    description="Shared utilities and common code for YTCaption microservices",
    author="YTCaption Team",
    packages=find_packages(),
    install_requires=[
        "redis>=5.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "fastapi>=0.100.0",
    ],
    python_requires=">=3.11",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
    ],
)
