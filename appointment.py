# /mnt/data/appointment.py
from flask import jsonify, request
def create_appointment_stub(data):
    """
    Minimal placeholder — in production integrate with real booking/calendar.
    Returns a simple confirmation payload.
    """
    return {
        "ok": True,
        "message": "Appointment request received. A provider will contact you.",
        "data": data
    }
