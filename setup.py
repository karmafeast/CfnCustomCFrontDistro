import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="CfnCustomCFrontDistro",
    version="0.0.1",
    author="karmafeast",
    author_email="karmafeast@gmail.com",
    description="AWS cloudformation CloudFront Distributions with OriginGroups support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/karmafeast/CfnCustomCFrontDistro",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
	py_modules=['CfnCustomCFrontDistro','CFrontClasses']
)