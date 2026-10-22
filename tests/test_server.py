import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
    "find_patient", "verify_sender", "get_patient_summary", "list_medications", "check_refill_eligibility",
    "prepare_refill_for_approval", "get_patient_appointments", "find_available_slots", "book_appointment",
    "reschedule_appointment", "cancel_appointment", "get_clinic_info", "resolve_date", "route_to_queue",
    "flag_suspicious_instruction", "draft_reply", "admin_reset_store", "admin_begin_message", "admin_export_state",
}


def _payload(result) -> dict:
    if getattr(result, "structured_content", None):
        sc = result.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    return json.loads(result.content[0].text)


async def _session_roundtrip():
    params = StdioServerParameters(command=sys.executable, args=["-m", "clinic_mcp.server"], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            info = _payload(await session.call_tool("get_clinic_info", {}))
            tomorrow = _payload(await session.call_tool("resolve_date", {"expression": "tomorrow"}))
            await session.call_tool("admin_begin_message", {"message_id": "T1", "from_name": "Mike", "from_contact": "555-0888", "channel": "sms"})
            meds = _payload(await session.call_tool("list_medications", {"verification_token": "vt_fake"}))
            return names, info, tomorrow, meds


def test_server_lists_tools_and_answers_over_stdio():
    names, info, tomorrow, meds = asyncio.run(_session_roundtrip())
    assert EXPECTED <= names
    assert info["info"]["today"] == "2026-11-09"
    assert tomorrow["start"] == "2026-11-10"
    assert meds["ok"] is False and "verif" in meds["reason"].lower()
