from graphql import graphql_sync

import frappe
from frappe_gql_adaptor.schema import get_graphql_schema


# TODO: refactor to cached value w/ redis (not lru)
schema = get_graphql_schema()


@frappe.whitelist(allow_guest=True)
def graphql_server():
	response = {}
	query, variables, operation_name = get_query()
	if not query:
		response["errors"] = [{"message": "No query was provided"}]
		frappe.local.response.update(response)
		return
	result = graphql_sync(
		schema=schema,
		source=query,
		variable_values=variables,
		operation_name=operation_name,
		middleware=[frappe.get_attr(m) for m in frappe.get_hooks("graphql_middlewares")],
		context_value=frappe._dict(),
		# execution_context_class=DeferredExecutionContext
	)
	if getattr(result, "data", None):
		response["data"] = result.data
	if getattr(result, "errors", None):
		response["errors"] = result.errors
	frappe.local.response.update(response)


def get_query() -> tuple[str | None, str | dict | None, str | None]:
	query = None
	variables = None
	operation_name = None
	if not hasattr(frappe.local, "request"):
		return query, variables, operation_name

	request = frappe.local.request
	content_type = request.content_type or ""

	if request.method == "GET":
		query = frappe.safe_decode(request.args.get("query"))
		variables = frappe.safe_decode(request.args.get("variables"))
		operation_name = frappe.safe_decode(request.args.get("operation_name"))
	elif request.method == "POST":
		# raise Exception("Please send in application/json")
		if "application/json" in content_type:
			graphql_request = frappe.parse_json(request.get_data(as_text=True))
			query = graphql_request.query
			variables = graphql_request.variables
			operation_name = graphql_request.operationName

		elif "multipart/form-data" in content_type:
			# Follows the spec here: https://github.com/jaydenseric/graphql-multipart-request-spec
			# This could be used for file uploads, single / multiple
			operations = frappe.parse_json(request.form.get("operations"))
			query = operations.get("query")
			variables = operations.get("variables")
			operation_name = operations.get("operationName")

			files_map = frappe.parse_json(request.form.get("map"))
			for file_key in files_map:
				file_instances = files_map[file_key]
				for file_instance in file_instances:
					path = file_instance.split(".")
					obj = operations[path.pop(0)]
					while len(path) > 1:
						obj = obj[path.pop(0)]

					obj[path.pop(0)] = file_key

	return query, variables, operation_name
