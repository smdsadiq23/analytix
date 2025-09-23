import frappe

def resolve_company(allow_unset=False, allow_sysmgr_unrestricted=True, explicit=None):
    """
    Return the company string to scope data to.

    Order:
      1) explicit (if passed in)
      2) User Default "Company"
      3) Global Defaults "default_company"
      4) if allow_sysmgr_unrestricted and user has System Manager -> None (no restriction)
      5) else -> throw unless allow_unset=True (then returns None)

    Usage:
        company = resolve_company()
        if company: conds.append("tor.company = %(company)s"); params['company'] = company
    """
    # If System Manager and unrestricted allowed
    if allow_sysmgr_unrestricted and "System Manager" in frappe.get_roles():
        # If caller gave an explicit company (e.g., filter), respect it; else unrestricted (None)
        if explicit:
            return explicit
        return None

    # 1) explicit value (e.g., from filters)
    if explicit:
        return explicit

    # 2) user's default company
    user_company = frappe.defaults.get_user_default("Company")
    if user_company:
        return user_company

    # 3) global default company (Global Defaults)
    global_default = frappe.db.get_single_value("Global Defaults", "default_company")
    if global_default:
        return global_default

    # 4) no company available
    if allow_unset:
        return None
    frappe.throw("No company configured for your user, and no Global Default company is set.", frappe.PermissionError)


def add_company_condition(conds, params, table_alias="tor", company=None):
    """
    Append a simple `table_alias.company = %(company)s` condition if company is truthy.
    Mutates conds (list[str]) and params (dict).
    """
    if company:
        conds.append(f"{table_alias}.company = %(company)s")
        params["company"] = company
