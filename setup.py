from setuptools import setup, find_packages

setup(
    name="satyahd",
    version="0.2.0",
    packages=find_packages(),
    package_data={
        "satyahd": ["py.typed"],
        "app": ["static/*"],
    },
    include_package_data=True,
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.28.0",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.2.0",
        "httpx>=0.27.0",
        "cryptography>=42.0.0",
        "python-multipart>=0.0.9",
        "pillow>=10.2.0",
        "numpy>=1.26.0",
    ],
    python_requires=">=3.10",
)
