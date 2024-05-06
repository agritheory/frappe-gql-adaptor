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

import frappe
from frappe.model import table_fields, display_fieldtypes
from frappe_gql_adaptor import resolvers

default_fields = [
	frappe._dict({"fieldname": "doctype", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "name", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "owner", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "creation", "reqd": True, "fieldtype": "Datetime", "options": ""}),
	frappe._dict({"fieldname": "modified", "reqd": True, "fieldtype": "Datetime", "options": ""}),
	frappe._dict({"fieldname": "modified_by", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "docstatus", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "idx", "reqd": True, "fieldtype": "Int", "options": ""}),
]

child_table_fields = [
	frappe._dict({"fieldname": "parent", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "parentfield", "reqd": True, "fieldtype": "Data", "options": ""}),
	frappe._dict({"fieldname": "parenttype", "reqd": True, "fieldtype": "Data", "options": ""}),
]


doctype_interface = GraphQLInterfaceType(
	"DocType",
	lambda: {
		"name": GraphQLField(
			GraphQLNonNull(GraphQLID),
		),
		# 'modified': GraphQLField(GraphQLNonNull(GraphQLID),),
	},
	# resolve_type='DocType',
	# description='Alias for frappe.get_doc'
)

link_interface = GraphQLInterfaceType(
	"Link",
	lambda: {
		"name": GraphQLField(
			GraphQLNonNull(GraphQLID),
		),
		# 'modified': GraphQLField(GraphQLNonNull(GraphQLID),),
	},
	# resolve_type='DocType',
	# description='Alias for frappe.get_doc'
)


def get_graphql_schema():
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
			if field.fieldtype in table_fields:
				_doctypes.append(field.options)
			if field.fieldtype == "Link":
				schema.shallow_doctypes.add(field.options)

	for doctype in sorted(_doctypes + doctype_schema):
		schema = build_schema(frappe.get_meta(doctype), schema)

	queries = get_queries(schema)
	mutations = get_mutations(schema)

	return GraphQLSchema(query=queries, mutation=mutations, types=list(schema.types.values()))


def build_schema(meta, schema):
	schema.schema_doctypes[meta.name] = frappe._dict({})
	if meta.name.replace(" ", "").replace("-", "") not in schema.shallow_doctypes:
		fields = default_fields
		if meta.istable:
			fields += child_table_fields
	fields += meta.fields
	for field in fields:
		if field.fieldtype in ("Link"):
			# continue
			link_name = f'{field.options.replace(" ", "").replace("-", "")}Link'
			if link_name not in schema.schema_doctypes.keys():
				schema = get_shallow_type(schema, field)
			schema.schema_doctypes[link_name] = frappe._dict({})
			schema.schema_doctypes[link_name][field.fieldname] = get_graphql_field(schema, field)

		if field.fieldtype in table_fields:
			continue

		elif field.fieldtype not in display_fieldtypes:
			if field.fieldtype != "Select":
				schema.schema_doctypes[meta.name][field.fieldname] = get_graphql_field(schema, field)

	gql_type = GraphQLObjectType(
		meta.name.replace(" ", "").replace("-", ""),
		schema.schema_doctypes[meta.name],
		interfaces=[doctype_interface, link_interface],
	)
	if gql_type not in schema.types:
		schema.types[meta.name.replace(" ", "").replace("-", "")] = gql_type

	return schema


# copied and modified from frappe-graphql
def get_graphql_field(schema, docfield):
	string_fieldtypes = [
		"Small Text",
		"Long Text",
		"Code",
		"Text Editor",
		"Markdown Editor",
		"HTML Editor",
		"Date",
		"Datetime",
		"Time",
		"Text",
		"Data",
		"Rating",
		"Read Only",
		"Attach",
		"Attach Image",
		"Signature",
		"Color",
		"Barcode",
		"Geolocation",
		"Duration",
	]
	int_fieldtypes = ["Int", "Long Int"]
	float_fieldtypes = ["Currency", "Float", "Percent", "Rating"]

	graphql_type = None
	if docfield.fieldname == "name":
		graphql_type = GraphQLID
	elif docfield.fieldtype == "Link":
		if docfield.options.replace(" ", "").replace("-", "") in schema.types:
			graphql_type = schema.types.get(docfield.options.replace(" ", "").replace("-", ""))
		else:
			graphql_type = get_interface(docfield)
	elif docfield.fieldtype in string_fieldtypes:
		graphql_type = GraphQLString
	elif docfield.fieldtype in int_fieldtypes:
		graphql_type = GraphQLInt
	elif docfield.fieldtype in float_fieldtypes:
		graphql_type = GraphQLFloat
	elif docfield.fieldtype == "Check":
		graphql_type = GraphQLBoolean
	elif docfield.fieldtype in table_fields:
		if docfield.options.replace(" ", "").replace("-", "") in schema.types:
			graphql_type = schema.types.get(docfield.options.replace(" ", "").replace("-", ""))
		else:
			graphql_type = GraphQLList(get_interface(docfield))
	elif docfield.fieldtype == "Select":
		select_enum = docfield.parent.replace(" ", "").replace("-", "")
		select_enum += docfield.fieldname.replace("_", " ").title().replace(" ", "")
		select_enum += "Options"
		if select_enum not in schema.shallow_doctypes:
			schema.shallow_doctypes.add(select_enum)
			options = docfield.options.split("\n")
			graphql_type = GraphQLEnumType(
				select_enum,
				{
					value.replace(" ", "").replace("-", ""): GraphQLEnumValue(index, description=value)
					for index, value in enumerate(options)
				},
			)

	if docfield.reqd:
		graphql_type = GraphQLNonNull(graphql_type)

	return GraphQLField(
		graphql_type,
		description=docfield.label or docfield.options.replace("_", " ").title().replace(" ", ""),
	)


def get_shallow_type(schema, field):
	shallow_type = get_interface(field)
	schema.schema_doctypes[str(shallow_type)] = frappe._dict()
	schema.types[field.options.replace(" ", "").replace("-", "")] = shallow_type
	gql_type = GraphQLObjectType(
		str(shallow_type), schema.schema_doctypes[str(shallow_type)], interfaces=[link_interface]
	)
	return schema


def get_interface(docfield):
	return GraphQLObjectType(
		f'{docfield.options.replace(" ", "").replace("-", "")}Link',
		lambda: {"name": GraphQLNonNull(GraphQLID)},
		interfaces=[link_interface],
		# resolve_type=lambda obj, info, args: f'{docfield.options.replace(" ", "").replace("-", "")}Link',
	)


def get_queries(schema):
	queries = {}
	queries["getMeta"] = get_stonecrop_meta()
	for key, doctype in schema.types.items():
		queries[f"list{key}"] = GraphQLField(
			GraphQLList(doctype), {"name": GraphQLArgument(GraphQLString)}, resolve=resolvers.get_list
		)
		if isinstance(doctype, GraphQLObjectType):
			queries[f"get{key}"] = GraphQLField(
				doctype, {"name": GraphQLArgument(GraphQLString)}, resolve=resolvers.get_doc
			)

	return GraphQLObjectType(name="Query", fields=queries)


def get_mutations(schema):
	mutations = {}
	for key, doctype in schema.types.items():
		if isinstance(doctype, GraphQLObjectType):
			mutations[f"save{key}"] = GraphQLField(
				doctype, {"name": GraphQLArgument(GraphQLString)}, resolve=resolvers.save_doc
			)
			mutations[f"delete{key}"] = GraphQLField(
				doctype, {"name": GraphQLArgument(GraphQLString)}, resolve=resolvers.delete_doc
			)

	return GraphQLObjectType("Mutation", lambda: mutations)


def get_stonecrop_meta():
	return GraphQLField(
		GraphQLObjectType(
			"getMeta",
			lambda: {
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

	# 		},
	# 		args={
	# 			'doctype': GraphQLArgument(GraphQLString, description='Doctype name', resolve=resolvers.get_meta)
	# 		}
	# 	),
	# )

	#   'hero': GraphQLField(character_interface, args={
	#       'episode': GraphQLArgument(episode_enum, description=(
	#           'If omitted, returns the hero of the whole saga.'
	#           ' If provided, returns the hero of that particular episode.'))},
	#       resolve=get_hero),
