import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="githubgql", # Replace with your own username
    version="0.0.3",
    author="Mark Bestavros",
    author_email="markbest@bu.edu",
    description="Python library for GraphQL API actions on Github",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/actions-automation/githubgql",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
