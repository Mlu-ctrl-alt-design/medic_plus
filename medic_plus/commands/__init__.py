"""Bench commands for Medic Plus.

Each command is a thin click wrapper over a function in
`medic_plus.api.terminology_import`. Subprocess-style integration
testing of click is brittle; the underlying functions are unit-tested
in `medic_plus.api.test_terminology_import`.
"""

from __future__ import annotations

import click
from frappe.commands import get_site, pass_context


def _run(context, fn_name: str, csv_path: str) -> None:
	site = get_site(context)
	import frappe
	frappe.connect(site=site)
	try:
		from medic_plus.api import terminology_import
		fn = getattr(terminology_import, fn_name)
		result = fn(csv_path)
		click.echo(
			f"[{result['system']}] created={result['created']} "
			f"updated={result['updated']}"
		)
	finally:
		frappe.destroy()


@click.command("import-icd10")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
@pass_context
def import_icd10_cmd(context, csv_path):
	"""Idempotent ICD-10-ZA Code Value bulk import from a (code,display) CSV."""
	_run(context, "import_icd10", csv_path)


@click.command("import-nappi")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
@pass_context
def import_nappi_cmd(context, csv_path):
	"""Idempotent NAPPI Code Value bulk import."""
	_run(context, "import_nappi", csv_path)


@click.command("import-loinc")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
@pass_context
def import_loinc_cmd(context, csv_path):
	"""Idempotent LOINC Code Value bulk import."""
	_run(context, "import_loinc", csv_path)


@click.command("import-ucum")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
@pass_context
def import_ucum_cmd(context, csv_path):
	"""Idempotent UCUM Code Value bulk import."""
	_run(context, "import_ucum", csv_path)


@click.command("import-atc")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
@pass_context
def import_atc_cmd(context, csv_path):
	"""Idempotent ATC Code Value bulk import."""
	_run(context, "import_atc", csv_path)


@click.command("import-snomed")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
@pass_context
def import_snomed_cmd(context, csv_path):
	"""Idempotent SNOMED-CT-ZA-stub Code Value bulk import.

	Production import of the full SNOMED CT-ZA catalogue is gated on
	IHTSDO Affiliate licence procurement (Phase 5.6 / issue #38). Until
	then, this stub system holds a small placeholder seed.
	"""
	_run(context, "import_snomed_stub", csv_path)


commands = [
	import_icd10_cmd,
	import_nappi_cmd,
	import_loinc_cmd,
	import_ucum_cmd,
	import_atc_cmd,
	import_snomed_cmd,
]
