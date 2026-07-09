from setuptools import setup, find_packages

setup(
    name="polycrit_extractor",
    version="0.1.0",
    description="Extract critical/non-critical LCCC conditions and experimental settings from PDF papers.",
    packages=find_packages(),
    install_requires=[
        "anthropic>=0.75.0",
        "openpyxl>=3.1.0",
        "pypdf>=5.0.0",
    ],
    python_requires=">=3.9",
)
