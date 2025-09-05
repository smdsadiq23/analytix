# AnalytiX/analytix/fixtures.py

import frappe
import json
import os

def after_install():
    """
    Called after app install or bench migrate
    """
    print("🔁 Starting import of Insights objects...")
    ensure_data_source()
    load_insights_objects()
    print("✅ Insights dashboards and queries imported successfully!")

def ensure_data_source():
    """
    Ensure 'Default' Insights Data Source exists
    """
    data_source_name = "Default"

    if frappe.db.exists("Insights Data Source v3", data_source_name):
        print(f"ℹ️ Insights Data Source '{data_source_name}' already exists.")
        return

    try:
        ds = frappe.new_doc("Insights Data Source v3")
        ds.title = data_source_name
        ds.type = "Database"
        ds.database_type = "MariaDB"
        ds.database_name = frappe.conf.db_name
        ds.insert(ignore_permissions=True)
        frappe.db.commit()
        print(f"✅ Created Insights Data Source: {data_source_name}")
    except Exception as e:
        frappe.log_error(e, "AnalytiX: Data Source Creation Failed")
        print(f"❌ Failed to create Data Source: {str(e)}")

def load_insights_objects():
    """
    Load Queries and Dashboards from JSON files in /fixtures
    """
    app_path = frappe.get_app_path("AnalytiX")
    fixtures_path = os.path.join(app_path, "fixtures")

    imports = [
        ("queries", "Query"),
        ("dashboards", "Dashboard")
    ]

    for folder, doctype in imports:
        folder_path = os.path.join(fixtures_path, folder)
        if not os.path.exists(folder_path):
            print(f"⚠️ Folder not found: {folder_path}")
            continue

        print(f"\n📂 Loading {doctype}s from {folder}...")
        for fname in sorted(os.listdir(folder_path)):
            if not fname.endswith(".json"):
                continue

            file_path = os.path.join(folder_path, fname)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)

                if not isinstance(doc_data, dict):
                    print(f"⚠️ Invalid JSON format (not dict): {fname}")
                    continue

                name = doc_data.get("name")
                if not name:
                    print(f"⚠️ Missing 'name' in {fname}")
                    continue

                import_insights_doc(doctype, name, doc_data, file_path)

            except Exception as e:
                frappe.log_error(e, f"AnalytiX: Import Failed - {fname}")
                print(f"❌ Failed to import {fname}: {e}")

def import_insights_doc(doctype, name, doc_data, file_path):
    """
    Import or update a single Query or Dashboard
    """
    if frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        doc.update(doc_data)
        doc.save(ignore_permissions=True)
        print(f"🔄 Updated {doctype}: {name}")
    else:
        doc = frappe.get_doc(doc_data)
        doc.insert(ignore_permissions=True)
        print(f"➕ Created {doctype}: {name}")