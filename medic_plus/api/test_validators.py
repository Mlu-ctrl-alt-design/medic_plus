"""Unit tests for medic_plus.api.validators."""

import frappe
from frappe.tests.utils import FrappeTestCase

from medic_plus.api.validators import (
	validate_hpcsa_number,
	validate_practice_number,
	validate_sa_mobile,
)


def run_smoke():
	"""Lightweight runner for ad-hoc checks via `bench execute`.

	Not part of the formal test suite — use FrappeTestCase above for that.
	Returns a dict of counts; raises on any assertion failure.
	"""
	cases_ok = [
		(validate_hpcsa_number, "MP1234567", "MP1234567"),
		(validate_hpcsa_number, "  mp 1234567  ", "MP1234567"),
		(validate_hpcsa_number, "DP0123456", "DP0123456"),
		(validate_practice_number, "1234567", "1234567"),
		(validate_practice_number, " 1234567 ", "1234567"),
		(validate_sa_mobile, "0821234567", "+27821234567"),
		(validate_sa_mobile, "+27821234567", "+27821234567"),
		(validate_sa_mobile, "27821234567", "+27821234567"),
		(validate_sa_mobile, "082 123-4567", "+27821234567"),
	]
	cases_err = [
		(validate_hpcsa_number, "1234567"),
		(validate_hpcsa_number, "ZZ1234567"),
		(validate_hpcsa_number, "MP123ABCD"),
		(validate_hpcsa_number, ""),
		(validate_practice_number, "123456"),
		(validate_practice_number, "12345678"),
		(validate_practice_number, "MP12345"),
		(validate_practice_number, ""),
		(validate_sa_mobile, "08212345"),
		(validate_sa_mobile, "821234567"),
		(validate_sa_mobile, ""),
	]

	for fn, value, expected in cases_ok:
		got = fn(value)
		assert got == expected, f"{fn.__name__}({value!r}) -> {got!r}, expected {expected!r}"

	for fn, value in cases_err:
		try:
			got = fn(value)
		except frappe.ValidationError:
			continue
		raise AssertionError(f"{fn.__name__}({value!r}) -> {got!r}, expected ValidationError")

	return {"ok": len(cases_ok), "err": len(cases_err)}


class TestValidateHpcsaNumber(FrappeTestCase):
	def test_accepts_canonical_form(self):
		self.assertEqual(validate_hpcsa_number("MP1234567"), "MP1234567")

	def test_normalises_whitespace_and_case(self):
		self.assertEqual(validate_hpcsa_number("  mp 1234567  "), "MP1234567")

	def test_accepts_all_known_prefixes(self):
		for prefix in ("DP", "PS", "OT", "OP", "ST"):
			self.assertEqual(
				validate_hpcsa_number(f"{prefix}0123456"),
				f"{prefix}0123456",
			)

	def test_rejects_missing_prefix(self):
		with self.assertRaises(frappe.ValidationError):
			validate_hpcsa_number("1234567")

	def test_rejects_unknown_prefix(self):
		with self.assertRaises(frappe.ValidationError):
			validate_hpcsa_number("ZZ1234567")

	def test_rejects_non_numeric_tail(self):
		with self.assertRaises(frappe.ValidationError):
			validate_hpcsa_number("MP123ABCD")

	def test_rejects_empty(self):
		with self.assertRaises(frappe.ValidationError):
			validate_hpcsa_number("")


class TestValidatePracticeNumber(FrappeTestCase):
	def test_accepts_seven_digits(self):
		self.assertEqual(validate_practice_number("1234567"), "1234567")

	def test_strips_whitespace(self):
		self.assertEqual(validate_practice_number(" 1234567 "), "1234567")

	def test_rejects_six_digits(self):
		with self.assertRaises(frappe.ValidationError):
			validate_practice_number("123456")

	def test_rejects_eight_digits(self):
		with self.assertRaises(frappe.ValidationError):
			validate_practice_number("12345678")

	def test_rejects_letters(self):
		with self.assertRaises(frappe.ValidationError):
			validate_practice_number("MP12345")

	def test_rejects_empty(self):
		with self.assertRaises(frappe.ValidationError):
			validate_practice_number("")


class TestValidateSaMobile(FrappeTestCase):
	def test_accepts_local_form(self):
		self.assertEqual(validate_sa_mobile("0821234567"), "+27821234567")

	def test_normalises_plus_27(self):
		self.assertEqual(validate_sa_mobile("+27821234567"), "+27821234567")

	def test_normalises_27_prefix(self):
		self.assertEqual(validate_sa_mobile("27821234567"), "+27821234567")

	def test_strips_spaces_and_dashes(self):
		self.assertEqual(validate_sa_mobile("082 123-4567"), "+27821234567")

	def test_rejects_too_short(self):
		with self.assertRaises(frappe.ValidationError):
			validate_sa_mobile("08212345")

	def test_rejects_missing_leading_zero(self):
		with self.assertRaises(frappe.ValidationError):
			validate_sa_mobile("821234567")

	def test_rejects_empty(self):
		with self.assertRaises(frappe.ValidationError):
			validate_sa_mobile("")
