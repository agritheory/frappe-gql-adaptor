from _typeshed import Incomplete
from frappe_gql_adaptor.schema import get_graphql_schema as get_graphql_schema

schema: Incomplete

def graphql_server() -> None: ...
def get_query() -> tuple[str | None, str | dict | None, str | None]: ...
