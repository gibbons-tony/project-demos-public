from setuptools import setup, find_packages

setup(
    name="forecast_agent",
    version="0.1.0",
    packages=find_packages(include=['ml_lib', 'ml_lib.*']),
    install_requires=[
        # ml_lib only needs PySpark (already on Databricks)
        # Other deps (pandas, numpy) also pre-installed on Databricks
    ],
    description="Commodity price forecasting agent with PySpark ML pipelines",
    python_requires='>=3.8',
)
