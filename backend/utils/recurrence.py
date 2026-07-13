import calendar
from datetime import timedelta, date

SCHEDULE_TYPES = ('monthly', 'yearly', 'weekly')


def _clamped_date(year, month, day):
    """Le jour est ramené au dernier jour du mois s'il le dépasse (ex: 31 en février -> 28/29)."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def parse_weekdays(weekdays_str):
    """'1,3' -> {1, 3} (ISO : 1=lundi … 7=dimanche)."""
    if not weekdays_str:
        return set()
    return {int(x) for x in weekdays_str.split(',') if x.strip()}


def format_weekdays(weekdays):
    return ','.join(str(d) for d in sorted(set(weekdays)))


def next_occurrence(schedule_type, day_of_month, month_of_year, weekdays_str, after):
    """Première date STRICTEMENT après `after` qui respecte la planification."""
    if schedule_type == 'monthly':
        year, month = after.year, after.month
        candidate = _clamped_date(year, month, day_of_month)
        while candidate <= after:
            month += 1
            if month > 12:
                month = 1
                year += 1
            candidate = _clamped_date(year, month, day_of_month)
        return candidate

    if schedule_type == 'yearly':
        year = after.year
        candidate = _clamped_date(year, month_of_year, day_of_month)
        while candidate <= after:
            year += 1
            candidate = _clamped_date(year, month_of_year, day_of_month)
        return candidate

    if schedule_type == 'weekly':
        weekdays = parse_weekdays(weekdays_str)
        candidate = after + timedelta(days=1)
        if not weekdays:
            return candidate
        for _ in range(7):
            if candidate.isoweekday() in weekdays:
                return candidate
            candidate += timedelta(days=1)
        return candidate

    raise ValueError(f"schedule_type invalide : {schedule_type}")
