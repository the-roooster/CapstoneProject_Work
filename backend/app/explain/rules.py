"""Pure rules over user-day features and supplied event history."""

from datetime import datetime, timedelta, timezone
from typing import TypedDict
from zoneinfo import ZoneInfo

from app.config import settings


RULE_CONFIG = {
    "event_ids_limit": 200,
    "off_hours_min": 1, "off_hours_high_above": 10,
    "off_hours_severity": 15, "off_hours_high_severity": 30,
    "late_login_min_deviation": 0, "late_login_severity": 15,
    "mass_download_ratio": 3, "mass_download_high_ratio": 8,
    "mass_download_severity": 20, "mass_download_high_severity": 35,
    "download_zscore_min": 3, "download_zscore_severity": 20,
    "first_usb_severity": 25, "new_usb_serial_severity": 20,
    "new_device_severity": 20, "new_location_severity": 20,
    "failed_logins_min": 3, "failed_logins_high": 6,
    "failed_logins_severity": 15, "failed_logins_high_severity": 25,
    "mass_delete_min": 20, "mass_delete_severity": 30,
    "off_hours_margin": 1,
}


class Reason(TypedDict):
    code: str
    text: str
    severity: int
    event_ids: list[int]


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _local(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(settings.APP_TZ))


def explain(user, feat, baseline, events) -> list[Reason]:
    """Explain one feature day using events through that day, including history.

    baseline supplies download_mean and optional earlier known_devices and
    known_locations. Events require event_id, timestamp, activity and may carry
    device, location, and event_metadata (or metadata). They are never modified.
    """
    day = _get(feat, "date")
    if isinstance(day, str):
        day = datetime.fromisoformat(day).date()
    if isinstance(day, datetime):
        day = day.date()
    relevant = sorted(((_local(_get(event, "timestamp")), event) for event in events),
                      key=lambda pair: pair[0])
    today = [(stamp, event) for stamp, event in relevant if stamp.date() == day]
    previous = [(stamp, event) for stamp, event in relevant if stamp.date() < day]
    start, end = _get(user, "normal_login_start"), _get(user, "normal_login_end")
    devices = set(_get(baseline, "known_devices", ()))
    locations = set(_get(baseline, "known_locations", ()))
    if _get(user, "primary_device"):
        devices.add(_get(user, "primary_device"))
    if _get(user, "home_location"):
        locations.add(_get(user, "home_location"))
    devices.update(_get(e, "device") for _, e in previous if _get(e, "device"))
    locations.update(_get(e, "location") for _, e in previous if _get(e, "location"))
    reasons = []

    def ids(pairs):
        return [_get(e, "event_id") for _, e in pairs if _get(e, "event_id") is not None][:RULE_CONFIG["event_ids_limit"]]

    def add(code, text, severity, pairs):
        reasons.append(Reason(code=code, text=text, severity=severity, event_ids=ids(pairs)))

    def activity(name):
        return [(t, e) for t, e in today if _get(e, "activity") == name]

    off = [(t, e) for t, e in today if t.hour < start - RULE_CONFIG["off_hours_margin"]
           or t.hour > end + RULE_CONFIG["off_hours_margin"]]
    off_count = _get(feat, "off_hours_events", 0)
    if off_count >= RULE_CONFIG["off_hours_min"]:
        severity = RULE_CONFIG["off_hours_high_severity"] if off_count > RULE_CONFIG["off_hours_high_above"] else RULE_CONFIG["off_hours_severity"]
        add("OFF_HOURS", f"{off_count:g} actions outside normal hours ({start}:00–{end}:00)", severity, off)

    logins = activity("login")
    if _get(feat, "login_hour_deviation", 0) > RULE_CONFIG["late_login_min_deviation"] and logins:
        stamp = logins[0][0]
        add("LATE_LOGIN", f"Login at {stamp:%H:%M}, outside normal hours ({start}-{end})",
            RULE_CONFIG["late_login_severity"], [logins[0]])

    ratio = _get(feat, "download_ratio", 0)
    downloads = _get(feat, "downloads", 0)
    download_events = activity("file_download")
    if ratio >= RULE_CONFIG["mass_download_ratio"]:
        severity = RULE_CONFIG["mass_download_high_severity"] if ratio >= RULE_CONFIG["mass_download_high_ratio"] else RULE_CONFIG["mass_download_severity"]
        mean = _get(baseline, "download_mean", _get(user, "normal_download_count", 0))
        add("MASS_DOWNLOAD", f"Download count exceeded average by {ratio:.1f}× ({downloads:g} vs ~{mean:g})", severity, download_events)
    zscore = _get(feat, "download_zscore", 0)
    if zscore >= RULE_CONFIG["download_zscore_min"]:
        add("DOWNLOAD_ZSCORE", f"{zscore:.1f} standard deviations above this user's 14-day average",
            RULE_CONFIG["download_zscore_severity"], download_events)

    usb = activity("usb_connect")
    if usb:
        first = usb[0][0]
        threshold = first - timedelta(days=settings.USB_LOOKBACK_DAYS)
        had_usb = any(threshold <= stamp < first and _get(event, "activity") == "usb_connect"
                      for stamp, event in relevant)
        if not had_usb:
            add("FIRST_USB", f"First USB storage device use in {settings.USB_LOOKBACK_DAYS} days",
                RULE_CONFIG["first_usb_severity"], usb)
    if _get(feat, "new_usb_serial", 0):
        add("NEW_USB_SERIAL", "Activity from a previously unseen USB serial",
            RULE_CONFIG["new_usb_serial_severity"], usb)
    if _get(feat, "new_device", 0):
        add("NEW_DEVICE", "Activity from a never-seen device fingerprint",
            RULE_CONFIG["new_device_severity"], [(t, e) for t, e in today if _get(e, "device") and _get(e, "device") not in devices])
    if _get(feat, "new_location", 0):
        add("NEW_LOCATION", "Activity from a new geographic location",
            RULE_CONFIG["new_location_severity"], [(t, e) for t, e in today if _get(e, "location") and _get(e, "location") not in locations])
    failed = _get(feat, "failed_logins", 0)
    if failed >= RULE_CONFIG["failed_logins_min"]:
        severity = RULE_CONFIG["failed_logins_high_severity"] if failed >= RULE_CONFIG["failed_logins_high"] else RULE_CONFIG["failed_logins_severity"]
        add("FAILED_LOGINS", f"{failed:g} failed login attempts", severity, activity("login_failed"))
    deletes = _get(feat, "deletes", 0)
    if deletes >= RULE_CONFIG["mass_delete_min"]:
        add("MASS_DELETE", f"{deletes:g} files deleted in one day",
            RULE_CONFIG["mass_delete_severity"], activity("file_delete"))
    return sorted(reasons, key=lambda reason: reason["severity"], reverse=True)
