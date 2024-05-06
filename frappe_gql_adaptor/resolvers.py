import json

from redis_dict import RedisDict

import frappe
from frappe.modules import get_doc_path


def get_list(obj, info, *args):
	doctype = info.path.key.replace("list", "")
	fields = ["name"]
	# TODO:
	# implement lookup fields based on requested fields in query
	# implement filters and order by variable handling
	# implement pagination
	return frappe.get_all(doctype, filters=None, fields=fields)


def get_doc(obj, info, *args):
	print(info)
	return {}


def save_doc(*args):
	print(args)
	return {}


def delete_doc(*args):
	print(args)
	return {}


"""
def get_doc_resolver(obj, info, **kwargs):
	dt = get_singular_doctype(info.field_name)
	if is_single(dt):
		kwargs["name"] = dt

	dn = kwargs["name"]
	if not frappe.has_permission(doctype=dt, doc=dn):
		raise frappe.PermissionError(frappe._(f"No permission for {dt} {dn}"))

	doc = frappe.get_doc(dt, dn)
	doc.apply_fieldlevel_read_permissions()
	return doc
"""


def get_meta(self, info, doctype):
	d = RedisDict(namespace="gql")
	for _doctype in frappe.get_hooks(hook="graphql").get("doctypes"):
		if not frappe.conf.developer_mode and d.get(frappe.scrub(doctype)):
			continue
		module = frappe.get_value("DocType", _doctype, "module")
		doc_path = f'{get_doc_path(module, "doctype", _doctype)}/{frappe.scrub(_doctype)}_schema.json'
		with open(doc_path) as json_file:
			d[frappe.scrub(_doctype)] = json.load(json_file)
	return {
		"doctype": doctype,
		"schema": json.dumps(d.get(frappe.scrub(doctype)).get("schema")),
		"workflow": json.dumps(d.get(frappe.scrub(doctype)).get("workflow")),
		"actions": json.dumps(d.get(frappe.scrub(doctype)).get("actions")),
	}
