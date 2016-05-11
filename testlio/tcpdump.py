from datetime import datetime, timedelta
from time import sleep
import pytz
import threading


local = threading.local()


def init(tcpdump_file_name='./dump.txt', host='pubads.g.doubleclick.net', time_zone_name='EST'):
    local.tcpdump_file_name = tcpdump_file_name
    local.host = host
    local.timezone = pytz.timezone(time_zone_name)


def validate(find, from_offset_in_seconds=60, to_offset_in_seconds=60):
    assert local.tcpdump_file_name and local.host and local.timezone, \
        'You need to initialise the tcp dump validator before using it. For that you need to call tcpdump.init()'

    datetime_validate_started = _get_datetime_now()
    datetime_from = datetime_validate_started - timedelta(seconds=from_offset_in_seconds)
    datetime_to = datetime_validate_started + timedelta(seconds=to_offset_in_seconds)

    while _get_datetime_now() < datetime_to:
        tcpdump_lines = _read()
        for line in tcpdump_lines:
            if datetime_from < line['datetime'] < datetime_to and all(x in line['path'] for x in find):
                print('Found TCP dump entry - find=' + find + ', methodCalledOn=' + str(datetime_validate_started) + ', datetime_now=' + str(_get_datetime_now()))
                return True
        sleep(1)  # wait for one second before reading the file again

    print('TCP dump entry not found - find=' + find + ', methodCalledOn=' + str(datetime_validate_started) + ", from_offset_in_seconds=" + str(from_offset_in_seconds) + ", to_offset_in_seconds=" + str(to_offset_in_seconds))
    return False


def _read():
    with open(local.tcpdump_file_name, 'r') as tcpdump_file:
        file_content = []
        for line_string in tcpdump_file:
            parsed_line = _parse_line(line_string, local.host)
            if parsed_line:
                file_content.append(parsed_line)
        return file_content


def _parse_line(line_string, host_to_find=None):
    try:
        line = line_string.split(' ')

        host = line[5]
        if host != host_to_find:
            return

        return {
            'datetime': datetime.strptime(line[0] + line[1], '%Y-%m-%d%H:%M:%S'),
            'host': host,
            'path': line[8]
        }
    except:
        # print('Failed trying to parse line, skipping... [' + line_string + ']')
        return


def _get_datetime_now():
    datetime_now = datetime.now(local.timezone) + timedelta(hours=1)  # daylight savings time
    return datetime_now.replace(tzinfo=None)
