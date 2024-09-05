#!/bin/env python3

#
# MIT License
#
# Copyright (c) 2023-2024 x86dev
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

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
import getopt
import holidays
from random import randint
import sys

class TimesheetLaw:
    """
    Represents requirements by law.
    """
    def __init__(self):
        self.max_hours_per_day = 10
        self.min_pause_hours_per_workday = 1
        self.public_holidays_count_as_workdays  = True # For Germany at least.
        self.sick_leave_count_as_workdays       = True # Ditto.
        self.child_sick_leave_count_as_workdays = True # Ditto.

class TimesheetConfig:
    """
    Keeps a personal timesheet configuration.

    Tweak this to your likings.
    """
    def __init__(self):
        # Stuff which needs tweaking each month.
        self.vacation = []
        # Example:
        # for i in range(1, 14):
        #     self.vacation.append(date(2024, 7, 1) + timedelta(days = i))
        self.sick_leave = []
        # Example: self.sick_leave.append(date(2024, 12, 24))
        self.child_sick_leave = []
        self.hol = None
        self.cal = calendar.Calendar()
        self.law = TimesheetLaw()
        self.minutes_diff = timedelta(hours=0) # Overhours / minus hours from last month.
        self.max_pause_hours_per_day = 2
        self.min_overhours = 0 # Don't abuse this!
        self.max_overhours = 0 # Ditto.
        # Stuff which probably does not need tweaking each month.
        self.verbosity = 0
        self.givenname = 'John'
        self.surname = 'Doe'
        self.work_on_weekend_days = []
        self.workdays_per_week = 5
        self.hours_per_week = 39
        self.hours_per_day = self.hours_per_week / self.workdays_per_week
        self.round_to_minutes = 15
        self.min_hours_per_day = 6
        self.start_not_before_than = datetime.strptime("08:00:00", "%H:%M:%S")
        self.start_not_later_than = datetime.strptime("11:00:00", "%H:%M:%S")
        self.pause_not_before_than = datetime.strptime("12:00:00", "%H:%M:%S")
        self.pause_not_later_than = datetime.strptime("14:00:00", "%H:%M:%S")

class TimesheetState:
    """
    Keeps a timesheet state.
    """
    def __init__(self, config):
        self.businessdays_per_month = 0
        self.worked_total_td   = config.minutes_diff
        self.vacation_days = 0
        self.sick_leave_days = 0
        self.child_sick_leave_days = 0
        # Note: 4.3 means: A month is 4.3 weeks on average (52 weeks / 12 months a year).
        self.to_work_td  = timedelta(minutes=config.hours_per_week * 60 * 4.3)
        self.to_work_td += timedelta(minutes=randint(config.min_overhours * 60, config.max_overhours * 60))

class TimesheetDay:
    """
    Represents a single timesheet day.
    """
    def __init__(self):
        self.date = None
        self.worktime_start = None
        self.worktime_end = None
        self.worktime_td = None
        self.pause_start = None
        self.pause_end = None
        self.pause_td = None
        self.comments = ''
        self.is_workday = False
        self.is_weekend = False
        self.is_public_holiday = False
        self.is_vacation = False
        self.is_sick_leave = False
        self.is_child_sick_leave = False

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

def round_timedelta(time_delta, date_delta=timedelta(minutes=15), _to='average'):
    """
    Rounds a timedelta up/down/average (15 minutes by default).
    """
    f = (datetime.min + time_delta).time()
    my = datetime(1, 1, 1, hour=f.hour, minute=f.minute, second=f.second)
    datetime_rounded = round_time(my, date_delta)
    dt = timedelta(hours=datetime_rounded.hour, minutes=datetime_rounded.minute)
    return dt

def timedelta_to_time(time_delta):
    """
    Returns a time object from a timedelta object.
    """
    total_m, s = divmod(time_delta.seconds, 60)
    h, m = divmod(total_m, 60)
    return time(h, m, s)

def calc_day(config, state, day):
    """
    Returns a calculated day based from a given timesheet state.
    """
    if day.is_vacation:
        state.vacation_days += 1
    if day.is_sick_leave:
        state.sick_leave_days += 1
    if day.is_child_sick_leave:
        state.child_sick_leave_days += 1

    if day.is_public_holiday \
    or day.is_vacation \
    or day.is_sick_leave \
    or day.is_child_sick_leave:
        state.worked_total_td += timedelta(hours=config.hours_per_day)
        return day

    if not day.is_workday:
        return day

    worktime_start    = random_time(config.start_not_before_than, config.start_not_later_than)
    worktime_start_td = timedelta(hours=worktime_start.hour, minutes=worktime_start.minute)
    worktime_dur_td   = timedelta(minutes=randint(config.min_hours_per_day * 60, config.law.max_hours_per_day * 60))
    pause_start       = random_time(config.pause_not_before_than, config.pause_not_later_than)
    pause_start_td    = timedelta(hours=pause_start.hour, minutes=pause_start.minute)
    pause_dur_td      = timedelta(minutes=randint(config.law.min_pause_hours_per_workday * 60, config.max_pause_hours_per_day * 60))

    # Debug:
    #worktime_start_td = timedelta(hours=8, minutes=0)
    #worktime_dur_td = timedelta(hours=8, minutes=0)
    #pause_start_td = timedelta(hours=12, minutes=0)
    #pause_dur_td = timedelta(hours=1, minutes=0)

    if config.round_to_minutes:
        worktime_start_td = round_timedelta(worktime_start_td)
        worktime_dur_td   = round_timedelta(worktime_dur_td)
        pause_start_td    = round_timedelta(pause_start_td)
        pause_dur_td      = round_timedelta(pause_dur_td)
    worktime_end_td = worktime_start_td + worktime_dur_td + pause_dur_td
    worktime_start  = datetime.min + worktime_start_td
    worktime_end    = datetime.min + worktime_end_td
    pause_end_td    = pause_start_td + pause_dur_td
    pause_start     = datetime.min + pause_start_td
    pause_end       = datetime.min + pause_end_td
    if worktime_dur_td > state.to_work_td:
        worktime_dur_td = state.m_to_to_work
    worked_td       = worktime_end_td - worktime_start_td - pause_dur_td

    day.worktime_start = worktime_start
    day.worktime_end   = worktime_end
    day.worktime_td    = worked_td
    day.pause_start    = pause_start
    day.pause_end      = pause_end
    day.pause_td       = pause_dur_td

    state.worked_total_td += worked_td

    return day

def get_days(config, datetime_now):
    """
    Returns a tuple of monthly days and the number of business days within that month.

    Also respects weekend days, public holidays, vacation and sick days (in 'comments' key).
    """
    days = []
    number_businessdays = 0
    for cur_date in list(config.cal.itermonthdates(datetime_now.year, datetime_now.month)):
        cur_day = TimesheetDay()
        if cur_date.month != datetime_now.month:
            continue
        is_workday = False
        is_public_holiday = False
        is_weekend = False
        is_vacation = cur_date in config.vacation
        is_sick_leave = cur_date in config.sick_leave
        is_child_sick_leave = cur_date in config.child_sick_leave
        if cur_date in config.hol:
            is_public_holiday = config.hol.get(cur_date)
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
        elif is_weekend:
            cur_day.is_weekend = True
            cur_day.comments = 'Wochenende'
        elif is_vacation:
            cur_day.is_vacation = True
            cur_day.comments = 'Urlaub'
        elif is_sick_leave:
            cur_day.is_sick_leave = True
            cur_day.comments = 'Krankmeldung'
            if config.law.sick_leave_count_as_workdays:
                is_workday = True
        elif is_child_sick_leave:
            cur_day.is_child_sick_leave = True
            cur_day.comments = 'Krankmeldung (Kind krank)'
            if config.law.child_sick_leave_count_as_workdays:
                is_workday = True
        else: # Regular work day
            is_workday = True

        if is_workday:
            cur_day.is_workday = True
            number_businessdays += 1
        days.append(cur_day)
    return days, number_businessdays

def printHelp():
    """
    Prints syntax help.
    """
    print("--help or -h")
    print("    Prints this help text.")
    print("--month <MM>")
    print("    Specifies the month (01-12).")
    print("-v")
    print("    Increases logging verbosity. Can be specified multiple times.")
    print("--year <YYYY>")
    print("    Specifies the year (e.g. 2024).")
    print("\n")

def main():
    """
    Main function.
    """
    try:
        aOpts, _ = getopt.gnu_getopt(sys.argv[1:], "hv", \
            [ "help", "month=", "year=" ])
    except getopt.error as msg:
        print(msg)
        print("For help use --help")
        sys.exit(2)

    config = TimesheetConfig()
    state = TimesheetState(config)

    now = datetime.now()

    for o, a in aOpts:
        if o in ("-h", "--help"):
            printHelp()
            sys.exit(0)
        elif o in "--month":
            now = now.replace(month=int(a))
        elif o in "--year":
            now = now.replace(year=int(a))
        elif o in "-v":
            config.verbosity += 1
        else:
            assert False, "Unhandled option"

    config.hol = holidays.DE(years = now.year, subdiv='BE', language='de')

    timestamp = '%d-%02d' % (now.year, now.month)

    fh = open(f'WH-{config.givenname}-{config.surname}-{timestamp}.csv', mode='w')
    csv_writer = csv.writer(fh, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    csv_hdr    = dict(date='Date', worktime_start='Start', worktime_end='End', \
                    pause_start='Lunch Break Start', pause_end='Lunch Break End', \
                    comments='Comments')
    if config.verbosity:
        csv_hdr['pause_td'] = 'Pause Duration'
        csv_hdr['worktime_td'] = 'Working Duration'

    csv_writer.writerow(csv_hdr.values())

    month_days, business_days_per_month = get_days(config, now)
    for cur_day in month_days:
        day_final = calc_day(config, state, cur_day)
        csv_row = { 'date': '', 'worktime_start': '', 'worktime_end': '', 'pause_start': '', 'pause_end': '', \
                    'comments': '' }
        if config.verbosity:
            csv_row['pause_td'] = ''
            csv_row['worktime_td'] = ''
        csv_row['date'] = str(day_final.date)
        if cur_day.worktime_start:
            csv_row['worktime_start'] = day_final.worktime_start.strftime("%H:%M")
        if cur_day.worktime_end:
            csv_row['worktime_end'] = day_final.worktime_end.strftime("%H:%M")
        if cur_day.pause_start:
            csv_row['pause_start'] = day_final.pause_start.strftime("%H:%M")
        if cur_day.pause_end:
            csv_row['pause_end'] = day_final.pause_end.strftime("%H:%M")
        if  config.verbosity \
        and cur_day.pause_td:
            csv_row['pause_td'] = timedelta_to_time(day_final.pause_td).strftime("%H:%M")
        if  config.verbosity \
        and cur_day.worktime_td:
            csv_row['worktime_td'] = timedelta_to_time(day_final.worktime_td).strftime("%H:%M")
        csv_row['comments'] = day_final.comments
        csv_writer.writerow(csv_row.values())
        print(csv_row)

    hours_worked_total = state.worked_total_td.total_seconds() / 3600
    hours_required     = state.to_work_td.total_seconds() / 3600

    if config.verbosity:
        print("Business days this month: %d => %d hours this month"
              % (business_days_per_month, business_days_per_month * config.hours_per_day))

    print("Worked               : %d / %d hours: " % (hours_worked_total, hours_required,))
    print("Vacation days        : %d" % (state.vacation_days,))
    print("Sick leave days      : %d" % (state.sick_leave_days,))
    print("Child sick leave days: %d" % (state.child_sick_leave_days,))

    csv_row = {}
    csv_row['date'] = ''
    csv_row['worktime_start'] = ''
    csv_row['worktime_end'] = ''
    csv_row['pause_start'] = ''
    csv_row['pause_end'] = ''
    if config.verbosity:
        csv_row['pause_td'] = ''
        csv_row['worktime_td'] = hours_worked_total
    csv_row['comments'] = 'Total Working Time'
    csv_writer.writerow(csv_row.values())
    print(csv_row)

    csv_row = {}
    csv_row['date'] = ''
    csv_row['worktime_start'] = ''
    csv_row['worktime_end'] = ''
    csv_row['pause_start'] = ''
    csv_row['pause_end'] = ''
    if config.verbosity:
        csv_row['pause_td'] = ''
        csv_row['worktime_td'] = -(hours_required - hours_worked_total)
    csv_row['comments'] = 'Accumulated '
    csv_writer.writerow(csv_row.values())
    print(csv_row)


if __name__ == "__main__":
    main()