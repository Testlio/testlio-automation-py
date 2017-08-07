import threading
from datetime import datetime, timedelta, time
from time import sleep
import pytz
import re

local = threading.local()

ERRORS_CONTAINERS = []

def init(tcpdump_file_name='./dump.txt', host='pubads.g.doubleclick.net', time_zone_name='EST'):
    local.tcpdump_file_name = tcpdump_file_name
    local.host = host
    local.timezone = pytz.timezone(time_zone_name)


def validate(uri_contains=None, uri_not_contains=None,
             body_contains=None, body_not_contains=None,
             from_offset_in_seconds=None, to_offset_in_seconds=None,
             from_date=None, to_date=None,
             verbose=True):
    assert local.tcpdump_file_name and local.host and local.timezone, 'You need to initialise the tcp dump validator before using it. For that you need to call tcpdump_upgrade.init()'
    assert uri_contains or uri_not_contains or body_contains or body_not_contains, 'uri_contains or uri_not_contains body_contains or body_not_contains must be provided'
    assert from_offset_in_seconds or from_date, 'from_offset_in_seconds or from_date must be provided'
    assert to_offset_in_seconds or to_date, 'to_offset_in_seconds or to_date must be provided'

    datetime_validate_started = _get_datetime_now()
    datetime_from = datetime_validate_started - timedelta(
        seconds=from_offset_in_seconds) if from_offset_in_seconds else from_date
    datetime_to = datetime_validate_started + timedelta(
        seconds=to_offset_in_seconds) if to_offset_in_seconds else to_date

    valid_uri_contains = True
    valid_uri_not_contains = True
    if uri_contains:
        valid_uri_contains = _validate_contains(uri_contains, datetime_from, datetime_to)
    if uri_not_contains:
        valid_uri_not_contains = _validate_not_contains(uri_not_contains, datetime_from, datetime_to)

    valid_body_contains = True
    valid_body_not_contains = True
    if body_contains:
        valid_body_contains = _validate_contains_body(body_contains, datetime_from, datetime_to)
    if body_not_contains:
        valid_body_not_contains = _validate_not_contains_body(body_not_contains, datetime_from, datetime_to)

    error = ""
    if not valid_uri_contains or not valid_uri_not_contains or not valid_body_contains or not valid_body_not_contains:
        err = sorted(ERRORS_CONTAINERS, key=len)
        for i in range(0, len(err)):
            if len(str(err[i])) > 10:
                error = str(err[i])
                break

        if error == "":
            error = "records are absent"

    return valid_uri_contains and valid_uri_not_contains and valid_body_contains and valid_body_not_contains, error


def _validate_contains(uri_contains, datetime_from, datetime_to):
    if not isinstance(uri_contains, list):
        uri_contains = [uri_contains]

    while _get_datetime_now() < datetime_to:
        tcpdump_lines = _read()
        for line in tcpdump_lines:
            if datetime_from < line['datetime'] < datetime_to and _all_present(line['path'], uri_contains):
                return True
        sleep(1)  # wait for one second before reading the file again

    return False


def _validate_not_contains(uri_not_contains, datetime_from, datetime_to):
    if not isinstance(uri_not_contains, list):
        uri_not_contains = [uri_not_contains]

    while _get_datetime_now() < datetime_to:
        tcpdump_lines = _read()
        for line in tcpdump_lines:
            if datetime_from < line['datetime'] < datetime_to and _any_present(line['path'], uri_not_contains):
                return False
        sleep(1)  # wait for one second before reading the file again

    return True


def _validate_contains_body(body_contains, datetime_from, datetime_to):
    if not isinstance(body_contains, list):
        body_contains = [body_contains]

    while _get_datetime_now() < datetime_to:
        tcpdump_lines = _read()
        for line in tcpdump_lines:
            if datetime_from < line['datetime'] < datetime_to and _all_present(line['body'], body_contains):
                return True
        sleep(1)  # wait for one second before reading the file again

    return False


def _validate_not_contains_body(body_not_contains, datetime_from, datetime_to):
    if not isinstance(body_not_contains, list):
        body_not_contains = [body_not_contains]

    while _get_datetime_now() < datetime_to:
        tcpdump_lines = _read()
        for line in tcpdump_lines:
            if datetime_from < line['datetime'] < datetime_to and _any_present(line['body'], body_not_contains):
                return False
        sleep(1)  # wait for one second before reading the file again

    return True


def _any_present(source_string, strings_to_find):
    if not strings_to_find:
        return True
    if not source_string:
        return False

    count_found = 0
    len_array = len(strings_to_find)
    error_container = []
    for string_to_find in strings_to_find:
        if not bool(re.search(string_to_find, source_string)):
            count_found += 1
        else:
            error_container.append("Parameter '{0}' is presented in line [{1}]".format(str(string_to_find).replace('(&|$)', ''), source_string))
    ERRORS_CONTAINERS.append(error_container)
    return count_found == len_array


def _all_present(source_string, strings_to_find):
    if not strings_to_find:
        return True
    if not source_string:
        return False

    count_found = 0
    len_array = len(strings_to_find)
    error_container = []
    for string_to_find in strings_to_find:
        if bool(re.search(string_to_find, source_string)):
            count_found += 1
        else:
            search_key = str(string_to_find).split('=')[0]
            if bool(re.search(search_key + '=', source_string)):
                actual_key_value = re.search('(' + search_key + '=\S+)&|$', source_string).group(0).split('&')[0]
                error_container.append("Expected result is '{0}'. But actual result found is {1}. In line [{2}]".format(str(string_to_find).replace('(&|$)', ''), actual_key_value, source_string))
            else:
                error_container.append("Parameter '{0}' is absent in line [{1}]".format(str(string_to_find).replace('(&|$)', ''), source_string))

    ERRORS_CONTAINERS.append(error_container)
    return count_found == len_array


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
            'path': line[8],
            'body': line[10]
        }
    except:
        # print('Failed trying to parse line, skipping... [' + line_string + ']')
        return


def _get_datetime_now():
    datetime_now = datetime.now(local.timezone) + timedelta(hours=1)  # daylight savings time
    return datetime_now.replace(tzinfo=None)
