import frappe
from frappe.core.doctype.docfield.docfield import DocField
from frappe.model import display_fieldtypes as DISPLAY_FIELD_TYPES
from frappe.model import table_fields as TABLE_FIELDS
from frappe.model.meta import Meta
from graphql import (
	GraphQLArgument,
	GraphQLBoolean,
	GraphQLEnumType,
	GraphQLEnumValue,
	GraphQLField,
	GraphQLFloat,
	GraphQLID,
	GraphQLInt,
	GraphQLInterfaceType,
	GraphQLList,
	GraphQLNonNull,
	GraphQLObjectType,
	GraphQLSchema,
	GraphQLString,
)

from frappe_gql_adaptor import resolvers

DEFAULT_FIELDS = [
	frappe._dict({"fieldname": "doctype", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "name", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "owner", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "creation", "reqd": True, "fieldtype": "Datetime", "options": ""}),
	frappe._dict({"fieldname": "modified", "reqd": True, "fieldtype": "Datetime", "options": ""}),
	frappe._dict({"fieldname": "modified_by", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "docstatus", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "idx", "reqd": True, "fieldtype": "Int", "options": ""}),
]

CHILD_TABLE_FIELDS = [
	frappe._dict({"fieldname": "parent", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "parentfield", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "parenttype", "reqd": True, "fieldtype": "Data", "options": ""}),
]

INT_FIELDTYPES = ["Int", "Long Int"]
FLOAT_FIELDTYPES = ["Currency", "Float", "Percent", "Rating"]
STRING_FIELDTYPES = [
	"Attach Image",
	"Attach",
	"Barcode",
	"Code",
	"Color",
	"Data",
	"Date",
	"Datetime",
	"Duration",
	"Geolocation",
	"HTML Editor",
	"Long Text",
	"Markdown Editor",
	"Rating",
	"Read Only",
	"Signature",
	"Small Text",
	"Text Editor",
	"Text",
	"Time",
]


doctype_interface = GraphQLInterfaceType(
	name="DocType",
	fields={
		"name": GraphQLField(
			GraphQLNonNull(GraphQLID),
		),
		# 'modified': GraphQLField(GraphQLNonNull(GraphQLID),),
	},
	# resolve_type='DocType',
	# description='Alias for frappe.get_doc'
)

link_interface = GraphQLInterfaceType(
	name="Link",
	fields={
		"name": GraphQLField(
			GraphQLNonNull(GraphQLID),
		),
		# 'modified': GraphQLField(GraphQLNonNull(GraphQLID),),
	},
	# resolve_type='DocType',
	# description='Alias for frappe.get_doc'
)


def get_graphql_schema() -> GraphQLSchema:
	schema = frappe._dict(
		{
			"schema_doctypes": frappe._dict(),
			"shallow_doctypes": set(),
			"types": {},
		}
	)
	frappe_hooks = frappe.get_hooks(hook="graphql")
	_doctypes, doctype_schema = [], []
	for app in frappe_hooks:
		if isinstance(app, dict):
			doctype_schema.append(app.get('doctypes'))
	for doctype in sorted(doctype_schema):
		meta = frappe.get_meta(doctype)
		for field in meta.fields:
			if field.fieldtype in TABLE_FIELDS:
				_doctypes.append(field.options)
			elif field.fieldtype == "Link":
				schema.shallow_doctypes.add(field.options)

	for doctype in sorted(_doctypes + doctype_schema):
		schema = build_schema(frappe.get_meta(doctype), schema)

	queries = get_queries(schema)
	mutations = get_mutations(schema)

	return GraphQLSchema(query=queries, mutation=mutations, types=list(schema.types.values()))


def build_schema(meta: Meta, schema: frappe._dict) -> frappe._dict:
	fields: list[frappe._dict | DocField] = []
	meta_name = remove_whitespace(meta.name)
	schema.schema_doctypes[meta_name] = frappe._dict({})
	if meta_name not in schema.shallow_doctypes:
		fields = DEFAULT_FIELDS
		if meta.istable:
			fields += CHILD_TABLE_FIELDS
	fields += meta.fields
	for field in fields:
		if field.fieldtype in TABLE_FIELDS + DISPLAY_FIELD_TYPES:
			continue

		# TODO: how to handle dynamic link?
		if field.fieldtype == "Dynamic Link":
			continue

		# TODO: re-add when link fields are properly handled
		# if field.fieldtype in ("Link"):
		# 	# continue
		# 	link_name = get_link_name(field)
		# 	if link_name not in schema.schema_doctypes.keys():
		# 		schema = get_shallow_type(schema, field)
		# 	schema.schema_doctypes[link_name] = frappe._dict({})
		# 	schema.schema_doctypes[link_name][field.fieldname] = get_graphql_field(schema, field)

		schema.schema_doctypes[meta_name][field.fieldname] = get_graphql_field(schema, field)

	gql_type = GraphQLObjectType(
		name=meta_name,
		fields=schema.schema_doctypes[meta_name],
		# interfaces=[doctype_interface, link_interface],
	)

	if gql_type not in schema.types:
		schema.types[meta_name] = gql_type

	return schema


# copied and modified from frappe-graphql
def get_graphql_field(schema: frappe._dict, docfield: DocField) -> GraphQLField:
	graphql_type = None
	if docfield.fieldname == "name":
		graphql_type = GraphQLID
	elif docfield.fieldtype == "Link":
		# TODO: temporarily resolve to string; remove when link is implemented
		graphql_type = GraphQLString

		# TODO: handle link fields and add them to the schema
		# option = remove_whitespace(docfield.options)
		# if option in schema.types:
		# 	graphql_type = schema.types.get(option)
		# else:
		# 	graphql_type = get_interface(docfield)
	elif docfield.fieldtype in STRING_FIELDTYPES:
		graphql_type = GraphQLString
	elif docfield.fieldtype in INT_FIELDTYPES:
		graphql_type = GraphQLInt
	elif docfield.fieldtype in FLOAT_FIELDTYPES:
		graphql_type = GraphQLFloat
	elif docfield.fieldtype == "Check":
		graphql_type = GraphQLBoolean
	elif docfield.fieldtype in TABLE_FIELDS:
		option = remove_whitespace(docfield.options)
		if option in schema.types:
			graphql_type = schema.types.get(option)
		else:
			graphql_type = GraphQLList(get_interface(docfield))
	elif docfield.fieldtype == "Select":
		select_enum = remove_whitespace(docfield.parent)
		select_enum += docfield.fieldname.replace("_", " ").title().replace(" ", "")
		select_enum += "Options"
		if select_enum not in schema.shallow_doctypes:
			schema.shallow_doctypes.add(select_enum)
			options = docfield.options.split("\n")
			graphql_type = GraphQLEnumType(
				select_enum,
				{
					remove_whitespace(value): GraphQLEnumValue(value, description=value)
					for value in options
					if remove_whitespace(value)
				},
			)

	if docfield.reqd:
		graphql_type = GraphQLNonNull(graphql_type)

	# TODO: if a graphql_type isn't defined or available, what should happen here?
	# currently fails with "Field type must be an output type"
	return GraphQLField(
		graphql_type,
		description=docfield.label or docfield.options.replace("_", " ").title().replace(" ", ""),
	)


def get_shallow_type(schema: frappe._dict, field: DocField) -> frappe._dict:
	shallow_type = get_interface(field)
	schema.schema_doctypes[str(shallow_type)] = frappe._dict()
	schema.types[remove_whitespace(field.options)] = shallow_type
	# gql_type = GraphQLObjectType(
	# 	str(shallow_type), schema.schema_doctypes[str(shallow_type)], interfaces=[link_interface]
	# )
	return schema


def get_interface(docfield: DocField) -> GraphQLObjectType:
	return GraphQLObjectType(
		name=get_link_name(docfield),
		fields={"name": GraphQLNonNull(GraphQLID)},
		interfaces=[link_interface],
		# resolve_type=lambda obj, info, args: f'{remove_whitespace(docfield.options)}Link',
	)


def get_link_name(docfield: DocField) -> str:
	field_prefix = frappe.unscrub(docfield.fieldname).replace(" ", "")
	options_prefix = frappe.unscrub(docfield.options).replace(" ", "")
	if field_prefix == options_prefix:
		link_name = f"{field_prefix}Link"
	else:
		link_name = f"{field_prefix}{options_prefix}Link"
	return link_name


def get_queries(schema: frappe._dict) -> GraphQLObjectType:
	queries = {}
	queries["getMeta"] = get_stonecrop_meta()
	for key, doctype in schema.types.items():
		queries[f"list{key}"] = GraphQLField(
			GraphQLList(doctype),
			{"name": GraphQLArgument(GraphQLString)},
			resolve=resolvers.get_list,
		)
		if isinstance(doctype, GraphQLObjectType):
			queries[f"get{key}"] = GraphQLField(
				doctype, {"name": GraphQLArgument(GraphQLString)}, resolve=resolvers.get_doc
			)

	return GraphQLObjectType(name="Query", fields=queries)


def get_mutations(schema: frappe._dict) -> GraphQLObjectType:
	mutations = {}
	for key, doctype in schema.types.items():
		if isinstance(doctype, GraphQLObjectType):
			mutations[f"save{key}"] = GraphQLField(
				doctype, {"name": GraphQLArgument(GraphQLString)}, resolve=resolvers.save_doc
			)
			mutations[f"delete{key}"] = GraphQLField(
				doctype, {"name": GraphQLArgument(GraphQLString)}, resolve=resolvers.delete_doc
			)

	return GraphQLObjectType(name="Mutation", fields=mutations)


def get_stonecrop_meta() -> GraphQLField:
	return GraphQLField(
		GraphQLObjectType(
			name="getMeta",
			fields={
				"doctype": GraphQLField(
					GraphQLNonNull(GraphQLString),
				),
				"schema": GraphQLField(GraphQLNonNull(GraphQLString)),
				"workflow": GraphQLField(GraphQLNonNull(GraphQLString)),
				"actions": GraphQLField(GraphQLNonNull(GraphQLString)),
			},
		),
		{"doctype": GraphQLArgument(GraphQLString)},
		resolve=resolvers.get_meta,
	)


def remove_whitespace(text: str) -> str:
	return text.replace(" ", "").replace("-", "")
