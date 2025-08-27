from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="minismu_py",
    version="0.2.0",
    author="Undalogic",
    description="Python interface library for Undalogic miniSMU devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Undalogic/minismu_py",
    project_urls={
        "Bug Tracker": "https://github.com/Undalogic/minismu_py/issues",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.6",
    install_requires=[
        "pyserial>=3.5",
    ],
    extras_require={
        "dev": [
            "tqdm>=4.65.0",
        ],
    },
) 