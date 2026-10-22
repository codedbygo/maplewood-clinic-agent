import pytest

from clinic_mcp.policy.verification import verify_sender
from clinic_mcp.store import load_store

PATIENTS = load_store().patients


@pytest.mark.parametrize(
    "name,contact,dob,status,patient_id",
    [
        ("Robert Chen", "555-0102", None, "verified_patient", "P002"),
        ("Priya Raman", "Priya.Raman@Example.com", None, "verified_patient", "P007"),
        ("Robert Chen", "rchen.new@example.org", "1971-11-02", "verified_patient", "P002"),
        ("Anna Rossi", "555-0109", None, "verified_caregiver", "P009"),
        ("Sofia Rossi", "555-0109", None, "verified_patient", "P009"),
        ("Claire Ellis", "555-0177", None, "verified_caregiver", "P017"),
        ("Kevin O'Brien", "555-0114", None, "verified_patient", "P014"),
        ("Robert", "555-0102", None, "verified_patient", "P002"),
        ("Robert Chen", "(555) 0102", None, "verified_patient", "P002"),
    ],
)
def test_verified_senders(name, contact, dob, status, patient_id):
    r = verify_sender(PATIENTS, name, contact, dob)
    assert (r["status"], r["patient_id"]) == (status, patient_id), r["reason"]


def test_caregiver_relationship_is_reported():
    assert verify_sender(PATIENTS, "Anna Rossi", "555-0109")["relationship"] == "mother"


def test_wrong_dob_is_unverified_even_with_matching_name():
    r = verify_sender(PATIENTS, "Robert Chen", "rchen.new@example.org", "1971-11-20")
    assert r["status"] == "unverified"
    assert r["patient_id"] is None
    assert r["candidate_patient_ids"] == ["P002"]
    assert "date of birth" in r["reason"]


def test_wrong_dob_beats_contact_on_file():
    r = verify_sender(PATIENTS, "Robert Chen", "555-0102", "1971-11-20")
    assert r["status"] == "unverified"


def test_name_match_from_unknown_contact_without_dob_is_unverified():
    r = verify_sender(PATIENTS, "Robert Chen", "robert.chen@example.org")
    assert r["status"] == "unverified"
    assert r["candidate_patient_ids"] == ["P002"]


def test_stranger_is_unverified_with_no_candidates():
    for name, contact in [("Mike", "555-0888"), ("Jessica Parker", "jess.parker@example.net")]:
        r = verify_sender(PATIENTS, name, contact)
        assert r["status"] == "unverified"
        assert r["candidate_patient_ids"] == []


def test_shared_contact_with_unknown_name_is_ambiguous():
    # Review Focus 3: a spouse texting from the patient's phone gets no PHI.
    r = verify_sender(PATIENTS, "Mike", "555-0113")
    assert r["status"] == "ambiguous"
    assert r["patient_id"] is None
    assert r["candidate_patient_ids"] == ["P013"]


def test_caregiver_name_from_unknown_number_is_unverified():
    r = verify_sender(PATIENTS, "Claire Ellis", "555-0999")
    assert r["status"] == "unverified"
    assert r["candidate_patient_ids"] == ["P017"]


def test_blank_name_from_unique_contact_on_file_is_verified():
    r = verify_sender(PATIENTS, "", "555-0112")
    assert (r["status"], r["patient_id"]) == ("verified_patient", "P012")
