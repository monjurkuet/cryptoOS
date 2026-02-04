from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cryptoOS",
    version="1.0.0",
    author="cryptoOS Contributors",
    author_email="hello@cryptosharen.com",
    description="Comprehensive cryptocurrency data aggregation platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/monjurkuet/cryptoOS",
    packages=find_packages(exclude=["tests*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.31.0",
        "httpx>=0.25.0",
        "pydantic>=2.5.0",
        "pandas>=2.1.0",
        "numpy>=1.26.0",
        "aiohttp>=3.9.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0.0",
        "loguru>=0.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "mypy>=1.7.0",
            "ruff>=0.1.0",
            "black>=23.0.0",
            "isort>=5.12.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocstrings>=0.23.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cryptoOS=cryptoOS.__main__:main",
        ],
    },
    include_package_data=True,
    keywords=[
        "cryptocurrency",
        "bitcoin",
        "blockchain",
        "crypto",
        "on-chain",
        "defi",
        "data",
        "analytics",
    ],
    project_urls={
        "Bug Reports": "https://github.com/monjurkuet/cryptoOS/issues",
        "Funding": "https://github.com/sponsors/monjurkuet",
        "Source": "https://github.com/monjurkuet/cryptoOS",
        "Documentation": "https://monjurkuet.github.io/cryptoOS/",
    },
)
