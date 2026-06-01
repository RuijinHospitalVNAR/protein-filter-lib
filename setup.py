"""
Setup script for protein_filter_lib.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="protein-filter-lib",
    version="0.1.0",
    description="Independent protein design filter and quality assessment library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="RuijinHospitalVNAR",
    author_email="",
    url="https://github.com/RuijinHospitalVNAR/protein-filter-lib",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.20.0,<3.0.0",  # 兼容 AF3 环境（AF3 通常使用 numpy 1.x 或 2.x）
        "scipy>=1.7.0",
        "biopython>=1.79",
        "pandas>=1.3.0",
        "scikit-learn>=0.24.0",  # 用于聚类分析（KMeans, DBSCAN等）
    ],
    extras_require={
        "full": [
            "mdtraj>=1.9.0",  # 用于 pDockQ2 和 LIS 计算（如果安装失败，会回退到基础 pDockQ）
        ],
        "clustering": [
            "hdbscan>=0.8.27",  # 用于HDBSCAN聚类（如果缺失，可以使用kmeans或dbscan替代）
            "matplotlib>=3.3.0",  # 用于可视化（可选）
            "psutil>=5.8.0",  # 用于系统监控（可选）
        ],
        "dev": [
            "pytest>=7.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
)

