# SPDX-License-Identifier: Apache-2.0

import requests
import json
import os
import time
import types

class HTTPError(Exception):
    def __init__(self, reply):
        self.reply = reply

class GraphQLError(Exception):
    def __init__(self, errors):
        self.errors = errors

class TokenError(Exception):
    def __init__(self, error):
        self.error = error

# A multiple, nested depagination example: fetch all issues, PRs, and PR
# timeline items.
#
# query = """
# query($owner:String!, $name:String!, $cursor1:String, $cursor2:String, $cursor3:String) {
#   repository(owner:$owner, name:$name) {
#     issues(first:100, after:$cursor1) {
#       pageInfo { endCursor hasNextPage }
#       nodes {
#         number
#       }
#     }
#     pullRequests(first:100, after:$cursor2) {
#       pageInfo { endCursor hasNextPage }
#       nodes {
#         timelineItems(first:100, after:$cursor3) {
#           pageInfo { endCursor hasNextPage }
#           nodes {
#             __typename
#           }
#         }
#       }
#     }
#   }
# }
# """
#
# cursors = {
#     'cursor1': {
#         'path': ["repository", "issues"],
#     },
#     'cursor2': {
#         'path': ["repository", "pullRequests"],
#         'next': {
#             'cursor3': {
#                 'path': ["timelineItems"],
#             }
#         }
#     }
# }
#
# data = graphql(query, token=token, cursors=cursors, owner="org", name="repo")
#
# Your query:
#   * MUST have a `$cursor:String` variable (it MUST NOT be required!)
#   * MUST specify `after: $cursor` correctly
#   * MUST fetch `pageInfo { endCursor hasNextPage }`
#   * MUST have a `nodes` entity on the pagination object
#   * SHOULD fetch as many objects as you can (i.e. `first: 100`)
#
# Additionally, you MUST provide an appropriately-scoped Github access token
# to `graphql()` under the `token` input. Depending on the application, the
# default `GITHUB_TOKEN` may work; otherwise, a personal access token may be 
# required.
#
# The results of depagination are merged. Therefore, you receive one big output list.
# Similarly, the `pageInfo` object is removed from the result.
def graphql(
        query,
        token=None,
        accept="",
        max_retries=8,
        cursors=None,
        prev_path=None,
        **kwargs
    ):
    "Perform a GraphQL query."
    url = os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")
    params = { "query": query.strip(), "variables": json.dumps(kwargs) }
    headers = {}

    # Set Github authentication token, if available. If not, fail gracefully.
    if token is not None and len(token) > 0:
        headers["Authorization"] = f"token {token}"
    else:
        raise TokenError(error="""
No Github access token provided.
    """)

    # Set custom Accept headers, if specified as input.
    headers["Accept"] = accept

    # Do the request and check for HTTP errors.
    reply = requests.post(url, json=params, headers=headers)

    # Retry certain HTTP errors.
    retry_codes = [403, 429, 500, 502, 503, 504]
    attempted_retries = 0

    # If a mutation is being attempted, don't retry.
    if query.split("(")[0] != "mutation":
        while reply.status_code in retry_codes and attempted_retries < max_retries:
            backoff = 2 ** (attempted_retries - 1)
            print(f"githubgql: Retrying {reply.status_code} call with backoff {backoff}")
            time.sleep(backoff)
            reply = requests.post(url, json=params, headers=headers)
            attempted_retries += 1

    if reply.status_code != 200:
        raise HTTPError(reply)

    # Check for GraphQL errors.
    data = reply.json()
    if "errors" in data:
        raise GraphQLError(data["errors"])
    data = data["data"]

    # Do depagination.
    if cursors is None:
        return data
    for cursor in cursors.keys():
        # Cursors can simply be path lists. If they are, convert to dict.
        if isinstance(cursors[cursor], list):
            cursors[cursor] = {
                "path": cursors[cursor]
            }
        current_path = cursors[cursor]['path']
        if prev_path:
            current_path = prev_path + current_path

        obj = data
        for name in current_path:
            obj = obj[name]

        pi = obj.pop("pageInfo")
        if pi["hasNextPage"]:
            kwargs[cursor] = pi["endCursor"]
            next = graphql(query, token=token, accept=accept, max_retries=max_retries, cursors={cursor:cursors[cursor]}, prev_path=prev_path, **kwargs)
            for name in current_path:
                next = next[name]

            obj["nodes"].extend(next["nodes"])

        # If there are nested cursors, depaginate them too.
        if cursors[cursor].get('next') is not None and not pi["hasNextPage"]:
            for i in range(len(obj["nodes"])):
                if not prev_path:
                    current_path_nodes = current_path.copy()
                else:
                    current_path_nodes = prev_path.copy()

                current_path_nodes += ["nodes", i]

                # First, check if another recursive call is necessary to
                # fully depaginate.
                # This happens when
                # 1) a nested cursor has further nested cursors
                # 2) a nested cursor has more than one page
                node_data = data
                for name in current_path_nodes:
                    node_data = node_data[name]

                call_required = False
                for next_cursor in cursors[cursor]['next']:
                    if isinstance(cursors[cursor]['next'][next_cursor], list):
                        cursors[cursor]['next'][next_cursor] = {
                            "path": cursors[cursor]['next'][next_cursor]
                        }
                    page_to_check = node_data
                    for name in cursors[cursor]['next'][next_cursor]['path']:
                        page_to_check = page_to_check[name]

                    hasNextPage = page_to_check['pageInfo']['hasNextPage']
                    nextNextCursor = cursors[cursor]['next'][next_cursor].get('next')
                    if hasNextPage or nextNextCursor is not None:
                        call_required = True
                if not call_required:
                    continue

                # If another call is required, make it.
                next = graphql(query, token=token, accept=accept, max_retries=max_retries, cursors=cursors[cursor]['next'], prev_path=current_path_nodes, **kwargs)

                # Weld the depaginated data together.
                for next_cursor in cursors[cursor]['next']:
                    join_path = current_path_nodes + cursors[cursor]['next'][next_cursor]['path']

                    obj_nested = data
                    next_nested = next
                    for name in join_path:
                        obj_nested = obj_nested[name]
                        next_nested = next_nested[name]
                    obj_nested["nodes"] = next_nested["nodes"]
    return data
