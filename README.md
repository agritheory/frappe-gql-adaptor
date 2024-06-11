# Frappe GraphQL Adaptor

Based on ideas from [frappe_graphql](https://github.com/leam-tech/frappe_graphql).

## Installation

Add `frappe-gql-adaptor` as a python dependency in your Frappe project and install it via `bench`:

```bash
bench pip install frappe-gql-adaptor
```

or if you're using a requirements file:

```bash
bench setup requirements --python  # after adding it to your requirements file
```

## Usage

Configure the following keys in your app's `hooks.py` file:

```python
# define the parent doctypes that will be exposed to the GraphQL API; each doctype must also
# define a JSON file (`<doctype>_schema.json`) in its module folder with the following keys:
# - doctype (string): the name of the doctype
# - schema (list of dict): the Stonecrop schema
# - workflow (dict): an XState state machine definition
# - actions (dict): the actions that can be performed on the doctype
graphql = {
  "doctypes": [
    "<doctype_name>",
    "<doctype_name>",
  ],
}

# (optional) must point to a Frappe function that returns a tuple, list, or a MiddlewareManager
# instance from the graphql.execution.middlewares module
graphql_middlewares = [
  "<app_name>.graphql.middleware.FrappeGQLMiddleware"
]
```
