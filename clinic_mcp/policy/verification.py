"""Sender verification per clinic.json privacy_policy.

Verification = name + date of birth match, or the message comes from the phone/email on file.
Authorised caregivers ({name, relationship, phone}) are verified by caregiver name + caregiver phone.
A stated date of birth that does not match makes the sender unverified, whatever else matches.
"""

from __future__ import annotations

import re
import unicodedata


def _name(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text)).strip()


def _contact(text: str | None) -> str:
    text = (text or "").strip().casefold()
    return text if "@" in text else re.sub(r"\D", "", text)


def _contact_eq(a: str | None, b: str | None) -> bool:
    a, b = _contact(a), _contact(b)
    if not a or not b:
        return False
    if "@" in a or "@" in b:
        return a == b
    # Tolerate a country code prefix on one side.
    return a == b or (min(len(a), len(b)) >= 7 and (a.endswith(b) or b.endswith(a)))


def _name_eq(sender: str, on_file: str, allow_first_only: bool) -> bool:
    s, f = _name(sender), _name(on_file)
    if not s:
        return False
    if s == f:
        return True
    return allow_first_only and " " not in s and s == f.split(" ")[0]


def _result(status, patient_id=None, candidates=(), relationship=None, reason=""):
    return {
        "status": status,
        "patient_id": patient_id,
        "candidate_patient_ids": sorted(set(candidates)),
        "relationship": relationship,
        "reason": reason,
    }


def verify_sender(
    patients: dict[str, dict], from_name: str, from_contact: str, stated_dob: str | None = None
) -> dict:
    name_hits = [p for p in patients.values() if _name_eq(from_name, p["name"], False)]
    carer_name_hits = [
        p for p in patients.values()
        if p.get("authorised_caregiver") and _name_eq(from_name, p["authorised_caregiver"]["name"], False)
    ]

    if stated_dob and name_hits:
        dob_hits = [p for p in name_hits if p["dob"] == stated_dob]
        if not dob_hits:
            return _result(
                "unverified",
                candidates=[p["id"] for p in name_hits],
                reason="The stated date of birth does not match the record for this name, so the sender "
                "cannot be verified, even if the contact is on file.",
            )
        if len(dob_hits) == 1:
            p = dob_hits[0]
            return _result("verified_patient", p["id"], [p["id"]], reason="Name and date of birth match the record.")

    contact_patients = [p for p in patients.values() if _contact_eq(from_contact, p.get("phone")) or _contact_eq(from_contact, p.get("email"))]
    contact_carers = [
        p for p in patients.values()
        if p.get("authorised_caregiver") and _contact_eq(from_contact, p["authorised_caregiver"].get("phone"))
    ]

    if contact_patients or contact_carers:
        named = [p for p in contact_patients if _name_eq(from_name, p["name"], True)]
        if len(named) == 1:
            p = named[0]
            return _result("verified_patient", p["id"], [p["id"]], reason="Sender name matches and the contact is the patient's own phone/email on file.")
        carers = [p for p in contact_carers if _name_eq(from_name, p["authorised_caregiver"]["name"], True)]
        if len(carers) == 1:
            p = carers[0]
            rel = p["authorised_caregiver"].get("relationship")
            return _result(
                "verified_caregiver", p["id"], [p["id"]], rel,
                reason=f"Sender is the authorised caregiver ({rel}) on file for this patient, writing from the caregiver phone on file.",
            )
        everyone = contact_patients + contact_carers
        if not _name(from_name) and len({p["id"] for p in contact_patients}) == 1 and not contact_carers:
            p = contact_patients[0]
            return _result("verified_patient", p["id"], [p["id"]], reason="No name given; the contact is the patient's own phone/email on file.")
        return _result(
            "ambiguous",
            candidates=[p["id"] for p in everyone],
            reason="The contact is on file, but the sender's name matches neither the patient nor an authorised "
            "caregiver (for example a family member sharing a phone). Do not disclose anything; ask the patient to "
            "contact us directly or verify with name and date of birth.",
        )

    if name_hits or carer_name_hits:
        return _result(
            "unverified",
            candidates=[p["id"] for p in name_hits + carer_name_hits],
            reason="The name matches a record, but the message is not from the phone/email on file and no matching "
            "date of birth was given. Ask for the date of birth before sharing anything.",
        )
    return _result("unverified", reason="The sender does not match any patient or authorised caregiver on file.")
