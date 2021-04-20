# githubgql

Python library for GraphQL API interactions on Github Actions.

Basic example:

```python
from githubgql import githubgql

QUERY = """
query { 
  repository(owner: "github", name: "docs") {
    name
  }
}
"""

token = os.environ.get('BOT_TOKEN', None)

result = githubgql.graphql(QUERY, token)
```

More detailed examples are present in the source.

Packaged using tutorial on
[packaging.python.org](https://packaging.python.org/tutorials/packaging-projects/).
Uses [gh-action-pypi-publish](https://github.com/actions-automation/githubgql)
for automatic publishing.
