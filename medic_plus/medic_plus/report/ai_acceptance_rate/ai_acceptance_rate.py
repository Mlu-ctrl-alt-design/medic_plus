import frappe


def execute(filters=None):
    filters = filters or {}

    columns = [
        {
            "label": "Practice",
            "fieldname": "practice",
            "fieldtype": "Link",
            "options": "Practice",
            "width": 160,
        },
        {
            "label": "Practitioner",
            "fieldname": "practitioner",
            "fieldtype": "Link",
            "options": "Healthcare Practitioner",
            "width": 180,
        },
        {
            "label": "Feature",
            "fieldname": "feature",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Total Calls",
            "fieldname": "total",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Accepted / Edited",
            "fieldname": "accepted",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": "Discarded",
            "fieldname": "discarded",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Pending",
            "fieldname": "pending",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Acceptance Rate %",
            "fieldname": "acceptance_rate",
            "fieldtype": "Float",
            "width": 150,
        },
    ]

    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("DATE(creation) >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("DATE(creation) <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("practice"):
        conditions.append("practice = %(practice)s")
        values["practice"] = filters["practice"]

    if filters.get("practitioner"):
        conditions.append("practitioner = %(practitioner)s")
        values["practitioner"] = filters["practitioner"]

    if filters.get("feature"):
        conditions.append("feature = %(feature)s")
        values["feature"] = filters["feature"]

    where = " AND ".join(conditions) if conditions else "1=1"

    rows = frappe.db.sql(
        f"""
        SELECT
            practice,
            practitioner,
            feature,
            COUNT(*) AS total,
            SUM(CASE WHEN practitioner_action IN ('Accepted', 'Edited') THEN 1 ELSE 0 END) AS accepted,
            SUM(CASE WHEN practitioner_action = 'Discarded' THEN 1 ELSE 0 END) AS discarded,
            SUM(CASE WHEN practitioner_action = 'Pending' THEN 1 ELSE 0 END) AS pending
        FROM `tabAI Inference Log`
        WHERE {where}
        GROUP BY practice, practitioner, feature
        ORDER BY practice, practitioner, feature
        """,
        values,
        as_dict=True,
    )

    for row in rows:
        t = row.total or 0
        a = row.accepted or 0
        row["acceptance_rate"] = round(a / t * 100, 1) if t else 0.0

    if rows:
        total_all = sum(r.total or 0 for r in rows)
        accepted_all = sum(r.accepted or 0 for r in rows)
        rows.append(
            frappe._dict({
                "practice": "TOTAL",
                "practitioner": "",
                "feature": "",
                "total": total_all,
                "accepted": accepted_all,
                "discarded": sum(r.discarded or 0 for r in rows),
                "pending": sum(r.pending or 0 for r in rows),
                "acceptance_rate": round(accepted_all / total_all * 100, 1) if total_all else 0.0,
            })
        )

    return columns, rows
