from datetime import datetime, timedelta
from time import sleep
import pytz
import threading


local = threading.local()


def init(tcpdump_file_name='./dump.txt', ads_host='pubads.g.doubleclick.net', time_zone_name='EST'):
    local.tcpdump_file_name = tcpdump_file_name
    local.ads_host = ads_host
    local.timezone = pytz.timezone(time_zone_name)


def validate(origin, offset_in_seconds=60):
    assert local.tcpdump_file_name and local.ads_host and local.time_zone_name, \
        'You need to initialise the tcp dump validator before using it. For that you need to call tcpdump.init()'

    datetime_validate_started = datetime.now(local.timezone)
    datetime_from = datetime_validate_started - timedelta(seconds=offset_in_seconds)
    datetime_to = datetime_validate_started + timedelta(seconds=offset_in_seconds)

    while datetime.now(local.timezone) < datetime_to:
        tcpdump_lines = _read()
        for line in tcpdump_lines:
            if datetime_from < line['datetime'] < datetime_to and origin in line['path']:
                print('Found TCP dump entry - origin=' + origin + ', methodCalledOn=' + str(datetime_validate_started) + ', datetime_now=' + str(datetime.now(local.timezone)))
                return True
        sleep(1)  # wait for one second before reading the file again

    print('TCP dump entry not found - origin=' + origin + ', methodCalledOn=' + str(datetime_validate_started) + ", offset_in_seconds=" + str(offset_in_seconds))
    return False


def _read():
    with open(local.tcpdump_file_name, 'r') as tcpdump_file:
        file_content = []
        for line_string in tcpdump_file:
            parsed_line = _parse_line(line_string, [local.ads_host])
            if parsed_line:
                file_content.append(parsed_line)
        return file_content


def _parse_line(line_string, valid_hosts=None):
    try:
        line = line_string.split(' ')

        host = line[5]
        if valid_hosts and host not in valid_hosts:
            return

        return {
            'datetime': datetime.strptime(line[0] + line[1], '%Y-%m-%d%H:%M:%S'),
            'host': host,
            'path': line[8]
        }
    except:
        # print('Failed trying to parse line, skipping... [' + line_string + ']')
        return
