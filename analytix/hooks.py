app_name = "analytix"
app_title = "AnalytiX"
app_publisher = "CognitionX Logic India Private Limited"
app_description = "Reports, Dashboards and KPIs"
app_email = "support@cognitionx.tech"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "analytix",
# 		"logo": "/assets/analytix/logo.png",
# 		"title": "AnalytiX",
# 		"route": "/analytix",
# 		"has_permission": "analytix.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/analytix/css/analytix.css"
# app_include_js = "/assets/analytix/js/analytix.js"

# include js, css files in header of web template
# web_include_css = "/assets/analytix/css/analytix.css"
# web_include_js = "/assets/analytix/js/analytix.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "analytix/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "analytix/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "analytix.utils.jinja_methods",
# 	"filters": "analytix.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "analytix.install.before_install"
# after_install = "analytix.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "analytix.uninstall.before_uninstall"
# after_uninstall = "analytix.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "analytix.utils.before_app_install"
# after_app_install = "analytix.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "analytix.utils.before_app_uninstall"
# after_app_uninstall = "analytix.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "analytix.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"analytix.tasks.all"
# 	],
# 	"daily": [
# 		"analytix.tasks.daily"
# 	],
# 	"hourly": [
# 		"analytix.tasks.hourly"
# 	],
# 	"weekly": [
# 		"analytix.tasks.weekly"
# 	],
# 	"monthly": [
# 		"analytix.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "analytix.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "analytix.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "analytix.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["analytix.utils.before_request"]
# after_request = ["analytix.utils.after_request"]

# Job Events
# ----------
# before_job = ["analytix.utils.before_job"]
# after_job = ["analytix.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"analytix.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# AnalytiX/analytix/hooks.py

# after_migrate = [
#     "analytix.fixtures.after_install"
# ]


# fixtures = [
#     # Workbooks
#     {"dt": "Insights Workbook", "filters": [["title", "in", [
#         "Sales Order WB"
#     ]]]},
#     # Queries
#     {"dt": "Insights Query v3", "filters": [["title", "in", [
#         "Sales Order"
#     ]]]},
#     # Charts (Insights)
#     {"dt": "Insights Chart v3", "filters": [["name", "in", [
#         "65a3b37o9f"
#     ]]]},
#     # Dashboards (Insights)
#     {"dt": "Insights Dashboard v3", "filters": [["title", "in", [
#         "Sales Order Details"
#     ]]]},
#     # Optional: if your Insights screens reference Desk cards/charts
#     # {"dt": "Number Card", "filters": [["name", "in", ["Open SO", "Backorders"]]]},
#     # {"dt": "Dashboard Chart", "filters": [["name", "in", ["Bookings vs Billings"]]]},
# ]


# fixtures = [
#     # Workbooks
#     # {"dt": "Insights Workbook"}, Export only once and delete the json file from Fixtures after first deployment
#     # Queries
#     {"dt": "Insights Query v3"},
#     # Charts (Insights)
#     {"dt": "Insights Chart v3"},
#     # Dashboards (Insights)
#     {"dt": "Insights Dashboard v3"},
#     # Optional: if your Insights screens reference Desk cards/charts
#     # {"dt": "Number Card", "filters": [["name", "in", ["Open SO", "Backorders"]]]},
#     # {"dt": "Dashboard Chart", "filters": [["name", "in", ["Bookings vs Billings"]]]},
# ]