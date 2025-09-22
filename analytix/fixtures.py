# AnalytiX/analytix/fixtures.py
# Used only for Frappe Insights

import frappe

def after_install():
    """
    Called after app install or bench migrate
    Creates the default Insights Workbook with name = 1 if not exists
    """
    print("🔁 AnalytiX: Setting up default workbook...")
    create_default_workbook()
    print("✅ AnalytiX setup completed!")


def create_default_workbook():
    """
    Creates a default Insights Workbook with name = 1 and title = 'Default Workbook'
    Only if it doesn't already exist
    """
    workbook_name = 1  # Must be int to match DB schema (bigint)

    if frappe.db.exists("Insights Workbook", workbook_name):
        print(f"ℹ️ Insights Workbook '{workbook_name}' already exists. Skipping.")
        return

    try:
        wb = frappe.get_doc({
            "doctype": "Insights Workbook",
            "name": workbook_name,
            "title": "Default Workbook"
        })
        wb.insert(ignore_permissions=True)
        frappe.db.commit()
        print(f"✅ Created Insights Workbook: {workbook_name}")
    except Exception as e:
        frappe.log_error(e, "AnalytiX: Failed to create Workbook")
        print(f"❌ Failed to create Workbook: {str(e)}")