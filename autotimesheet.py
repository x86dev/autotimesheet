#!/bin/env python

#
# Creates a monthly CSV-based timesheet and outputs the file to the current directory.
# Defaults to German law requirements / holidays (state Berlin).
#
# Work in progress, not stable yet. Carefully check the output!
#
# Tweak the various classes below to fit your country / law requirements. Don't abuse this!
#
# Install requirements into a virtual environment via (bash):
#   pip install virtualenv
#   python -m venv .venv
#   source .venv/bin/activate
#   pip install holidays

import calendar
import csv
from datetime import datetime, date, time, timedelta
import holidays
from random import randint, randrange

class TimesheetConfig:
    """
    Keeps a personal timesheet configuration.

    Tweak this to your likings.
    """
    def __init__(self):
        # Stuff which needs tweaking each month.
        self.vacation = []
        self.minutes_diff = timedelta(hours=0) # Overhours / minus hours from last month.
        self.max_pause_hours_per_day = 2
        self.min_overhours = 0 # Don't abuse this!
        self.max_overhours = 0 # Ditto.
        # Stuff which probably does not need tweaking each month.
        self.givenname = 'John'
        self.surname = 'Doe'
        self.work_on_weekend_days = []
        self.workdays_per_week = 5
        self.hours_per_week = 39
        self.hours_per_day = self.hours_per_week / self.workdays_per_week
        self.round_to_minutes = 15
        self.min_hours_per_day = 5
        self.start_not_before_than = datetime.strptime("08:00:00", "%H:%M:%S")
        self.start_not_later_than = datetime.strptime("11:00:00", "%H:%M:%S")
        self.pause_not_before_than = datetime.strptime("12:00:00", "%H:%M:%S")
        self.pause_not_later_than = datetime.strptime("14:00:00", "%H:%M:%S")

class TimesheetLaw:
    """
    Represents requirements by law.
    """
    def __init__(self):
        self.max_hours_per_day = 10
        self.min_pause_hours_per_workday = 1
        self.public_holidays_count_as_workdays = True # For Germany at least.

class TimesheetState:
    """
    Keeps a timesheet state.
    """
    def __init__(self, config):
        self.businessdays_per_month = 0
        self.m_worked   = config.minutes_diff
        self.m_to_work  = timedelta(minutes=config.hours_per_week * 60 * 4) ## @todo Means weeks
        self.m_to_work += timedelta(minutes=randint(config.min_overhours * 60, config.max_overhours * 60))

class TimesheetDay:
    """
    Represents a single timesheet day.
    """
    def __init__(self):
        self.date = None
        self.time_start = None
        self.time_end = None
        self.pause_start = None
        self.pause_end = None
        self.td_worktime = None
        self.comments = ''
        self.is_workday = False
        self.is_weekend = False
        self.is_public_holiday = False


def to_timedelta(t: time) -> timedelta:
    return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)

def to_time(seconds: int) -> time:
    return (datetime.min + timedelta(seconds=seconds)).time()

def random_time(start_time: time, end_time: time) -> time:
    start = to_timedelta(start_time)
    end = to_timedelta(end_time)
    duration = (end - start).seconds
    random_offset = randint(0, duration)
    return to_time((start + timedelta(seconds=random_offset)).seconds)

# Taken from: https://stackoverflow.com/questions/3463930/how-to-round-the-minute-of-a-datetime-object/10854034#10854034
def round_time(dt=None, date_delta=timedelta(minutes=1), to='average'):
    """
    Rounds a datetime object to a multiple of a timedelta

    dt : datetime.datetime object, default now.
    dateDelta : timedelta object, we round to a multiple of this, default 1 minute.
    from:  http://stackoverflow.com/questions/3463930/how-to-round-the-minute-of-a-datetime-object-python
    """
    round_to = date_delta.total_seconds()
    if dt is None:
        dt = datetime.now()
    seconds = (dt - dt.min).seconds

    if seconds % round_to == 0 and dt.microsecond == 0:
        rounding = (seconds + round_to / 2) // round_to * round_to
    else:
        if to == 'up':
            # // is a floor division, not a comment on following line (like in javascript):
            rounding = (seconds + dt.microsecond/1000000 + round_to) // round_to * round_to
        elif to == 'down':
            rounding = seconds // round_to * round_to
        else:
            rounding = (seconds + round_to / 2) // round_to * round_to

    return dt + timedelta(0, rounding - seconds, - dt.microsecond)

def round_timedelta(time_delta, date_delta=timedelta(minutes=15), to='average'):
    """
    Rounds a timedelta up/down/average (15 minutes by default).
    """
    f = (datetime.min + time_delta).time()
    my = datetime(1, 1, 1, hour=f.hour, minute=f.minute, second=f.second)
    datetime_rounded = round_time(my, date_delta)
    dt = timedelta(hours=datetime_rounded.hour, minutes=datetime_rounded.minute)
    return dt

def calc_day(day, law, config, state):
    """
    Returns a calculated day based from a given timesheet state.
    """
    if not day.is_workday:
        return day

    if  not day.is_public_holiday \
    or  (        day.is_public_holiday
         and not law.public_holidays_count_as_workdays):
        time_start  = random_time(config.start_not_before_than, config.start_not_later_than)
        td_start    = timedelta(hours=time_start.hour, minutes=time_start.minute)
        td_worktime_dur = timedelta(minutes=randint(config.min_hours_per_day * 60, law.max_hours_per_day * 60))
        pause_start = random_time(config.pause_not_before_than, config.pause_not_later_than)
        td_pause_start = timedelta(hours=pause_start.hour, minutes=pause_start.minute)
        td_pause_dur   = timedelta(minutes=randint(law.min_pause_hours_per_workday * 60, config.max_pause_hours_per_day * 60))

        # Debug:
        #td_start    = timedelta(hours=8, minutes=0)
        #td_worktime_dur = timedelta(hours=8, minutes=0)
        #td_pause_start = timedelta(hours=12, minutes=0)
        #td_pause_dur = timedelta(hours=1, minutes=0)

        if config.round_to_minutes:
            td_start         = round_timedelta(td_start)
            td_worktime_dur  = round_timedelta(td_worktime_dur)
            td_pause_start   = round_timedelta(td_pause_start)
            td_pause_dur     = round_timedelta(td_pause_dur)
        td_end      = td_start + td_worktime_dur + td_pause_dur
        time_start  = datetime.min + td_start
        time_end    = datetime.min + td_end
        td_pause_end = td_pause_start + td_pause_dur
        pause_start = datetime.min + td_pause_start
        pause_end   = datetime.min + td_pause_end
        if td_worktime_dur > state.m_to_work:
            td_worktime_dur = state.m_to_to_work
        td_worked   = td_end - td_start - td_pause_dur

        day.time_start = time_start
        day.time_end = time_end
        day.pause_start = pause_start
        day.pause_end   = pause_end

        day.td_worktime = td_worked

        state.m_worked  += td_worked

    return day

def get_days(config, datetime_now):
    """
    Returns a tuple of monthly days and the number of business days within that month.

    Also respects weekend days and public holidays (in 'comments' key).
    """
    days = []
    number_businessdays = 0
    for cur_date in list(cal.itermonthdates(datetime_now.year, datetime_now.month)):
        cur_day = TimesheetDay()
        if cur_date.month != datetime_now.month:
            continue
        is_workday = False
        is_public_holiday = False
        is_weekend = False
        if cur_date in holidays:
            is_public_holiday = holidays.get(cur_date)
        workday = None
        iso_weekday = cur_date.isoweekday()
        if iso_weekday <= 5 \
        or iso_weekday in config.work_on_weekend_days:
            workday = date
        else:
            is_weekend = True

        cur_day.date = cur_date
        if is_public_holiday:
            cur_day.comments = 'Feiertag: ' + is_public_holiday
            cur_day.is_public_holiday = is_public_holiday is not None
            if law.public_holidays_count_as_workdays:
                is_workday = True
        elif is_weekend:
            cur_day.is_weekend = True
            cur_day.comments = 'Wochenende'
        else: # Regular work day
            is_workday = True

        if is_workday:
            cur_day.is_workday = True
            number_businessdays += 1
        days.append(cur_day)
    return days, number_businessdays

now = datetime.now()
holidays = holidays.DE(years = now.year, subdiv='BE', language='de')

cal = calendar.Calendar()

law = TimesheetLaw()
config = TimesheetConfig()
state = TimesheetState(config)

timestamp = '%d-%02d' % (now.year, now.month)

fh = open(f'WH-{config.givenname}-{config.surname}-{timestamp}.csv', mode='w')
csv_writer = csv.writer(fh, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
csv_hdr    = dict(date='Date', time_start='Start', time_end='End', \
                  pause_start='Lunch Break Start', pause_end='Lunch Break End', \
                  td_worktime='Working Time', comments='Comments')
csv_writer.writerow(csv_hdr.values())

month_days, business_days_per_month = get_days(config, now)
for cur_day in month_days:
    day_final = calc_day(cur_day, law, config, state)
    csv_row = { 'date': '', 'time_start': '', 'time_end': '', 'pause_start': '', 'pause_end': '', \
                'td_worktime': '', 'comments': '' }
    csv_row['date'] = str(day_final.date)
    if cur_day.time_start:
        csv_row['time_start'] = day_final.time_start.strftime("%H:%M:%S")
    if cur_day.time_end:
        csv_row['time_end'] = day_final.time_end.strftime("%H:%M:%S")
    if cur_day.pause_start:
        csv_row['pause_start'] = day_final.pause_start.strftime("%H:%M:%S")
    if cur_day.pause_end:
        csv_row['pause_end'] = day_final.pause_end.strftime("%H:%M:%S")
    if cur_day.td_worktime:
        csv_row['td_worktime'] = day_final.td_worktime.seconds / 3600
    csv_row['comments'] = day_final.comments
    csv_writer.writerow(csv_row.values())
    print(csv_row)

hours_worked_total = state.m_worked.total_seconds() / 3600
hours_required     = state.m_to_work.total_seconds() / 3600

print("Business days this month: %d => %d hours this month" % (business_days_per_month, business_days_per_month * config.hours_per_day))
print("Required worktime (hours): ", hours_required)
print("Actual worktime (hours): ", hours_worked_total)

csv_row = {}
csv_row['date'] = ''
csv_row['time_start'] = ''
csv_row['time_end'] = ''
csv_row['pause_start'] = ''
csv_row['pause_end'] = ''
csv_row['td_worktime'] = hours_worked_total
csv_row['comments'] = 'Total Working Time'
csv_writer.writerow(csv_row.values())
print(csv_row)

csv_row = {}
csv_row['date'] = ''
csv_row['time_start'] = ''
csv_row['time_end'] = ''
csv_row['pause_start'] = ''
csv_row['pause_end'] = ''
csv_row['td_worktime'] = -(hours_required - hours_worked_total)
csv_row['comments'] = 'Accumulated '
csv_writer.writerow(csv_row.values())
print(csv_row)
