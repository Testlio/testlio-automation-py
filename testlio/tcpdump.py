import threading
import re
import pytz
from datetime import datetime, timedelta
from time import sleep

local = threading.local()


class SearchOn():
    PATH = 'path'
    BODY = 'body'


def init(tcpdump_file_name='./dump.txt', host='pubads.g.doubleclick.net', time_zone_name='EST'):
    local.tcpdump_file_name = tcpdump_file_name
    local.host = host
    local.timezone = pytz.timezone(time_zone_name)


def validate(uri_contains=None, uri_not_contains=None,
             from_offset_in_seconds=None, to_offset_in_seconds=None,
             from_date=None, to_date=None,
             verbose=True):
    assert local.tcpdump_file_name and local.host and local.timezone, 'You need to initialise the tcp dump validator before using it. For that you need to call tcpdump.init()'
    assert uri_contains or uri_not_contains, 'uri_contains or uri_not_contains must be provided'
    assert from_offset_in_seconds or from_date, 'from_offset_in_seconds or from_date must be provided'
    assert to_offset_in_seconds or to_date, 'to_offset_in_seconds or to_date must be provided'

    datetime_validate_started = _get_datetime_now()
    datetime_from = datetime_validate_started - timedelta(seconds=from_offset_in_seconds) if from_offset_in_seconds else from_date
    datetime_to = datetime_validate_started + timedelta(seconds=to_offset_in_seconds) if to_offset_in_seconds else to_date

    # valid = None
    if uri_contains:
        valid = _validate_contains(uri_contains, datetime_from, datetime_to)
    else:
        valid = _validate_not_contains(uri_not_contains, datetime_from, datetime_to)

    if verbose:
        if valid:
            print('>> TCP dump validation succeeded - uri_contains={0}, uri_not_contains={1}, methodCalledOn={2}, datetime_now={3}'.format(uri_contains, uri_not_contains, datetime_validate_started, _get_datetime_now()))
        else:
            print('>> TCP dump validation failed - uri_contains={0}, uri_not_contains={1}, methodCalledOn={2}, from_offset_in_seconds={3}, to_offset_in_seconds={4}'.format(uri_contains, uri_not_contains, datetime_validate_started, from_offset_in_seconds, to_offset_in_seconds))

    return valid


def validate_regex(regex_pattern=None, search_on=SearchOn.PATH,
                   from_offset_in_seconds=None, to_offset_in_seconds=None,
                   from_date=None, to_date=None,
                   verbose=True):
    assert local.tcpdump_file_name and local.host and local.timezone, 'You need to initialise the tcp dump validator before using it. For that you need to call tcpdump.init()'
    assert regex_pattern, 'regex_pattern must be provided'
    assert from_offset_in_seconds or from_date, 'from_offset_in_seconds or from_date must be provided'
    assert to_offset_in_seconds or to_date, 'to_offset_in_seconds or to_date must be provided'

    datetime_validate_started = _get_datetime_now()
    datetime_from = datetime_validate_started - timedelta(seconds=from_offset_in_seconds) if from_offset_in_seconds else from_date
    datetime_to = datetime_validate_started + timedelta(seconds=to_offset_in_seconds) if to_offset_in_seconds else to_date

    valid = _validate_regex(regex_pattern, search_on, datetime_from, datetime_to)

    if verbose:
        if valid:
            print('[INFO ] TCP dump validation succeeded - regex_pattern={0}, search_on={1}, methodCalledAt={2}, datetime_now={3}'
                  .format(regex_pattern, search_on, datetime_validate_started, _get_datetime_now()))
        else:
            print('[ERROR] TCP dump validation failed - regex_pattern={0}, search_on={1}, methodCalledAt={2}, from_offset_in_seconds={3}, to_offset_in_seconds={4}'
                  .format(regex_pattern, search_on, datetime_validate_started, from_offset_in_seconds, to_offset_in_seconds))

    return valid


def _validate_regex(regex_pattern, search_on, datetime_from, datetime_to):
    while _get_datetime_now() < datetime_to:
        tcpdump_lines = _read()
        for line in tcpdump_lines:
            if datetime_from < line['datetime'] < datetime_to and bool(re.search(regex_pattern, line[search_on])):
                return True
        sleep(1)  # wait for one second before reading the file again

    return False


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


def _any_present(source_string, strings_to_find):
    if not strings_to_find or not source_string:
        return True

    return any(string_to_find in source_string for string_to_find in strings_to_find)


def _all_present(source_string, strings_to_find):
    if not strings_to_find:
        return True
    if not source_string:
        return False

    return all(string_to_find in source_string for string_to_find in strings_to_find)


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

        body = ''
        if len(line) >= 10:
            body = line[10]

        return {
            'datetime': datetime.strptime(line[0] + line[1], '%Y-%m-%d%H:%M:%S'),
            'host': host,
            'path': line[8],
            'body': body
        }
    except:
        # print('Failed trying to parse line, skipping... [' + line_string + ']')
        return


def _get_datetime_now():
    datetime_now = datetime.now(local.timezone) + timedelta(hours=1)  # daylight savings time
    return datetime_now.replace(tzinfo=None)


class Pattern():
    PARAM_DELIMITER = '(&|$)'  # & or end of string marks the end of a param value


    @staticmethod
    def exists(param_name):
        # regex example: param_name=[^&]+
        return param_name

    @staticmethod
    def not_blank(param_name):
        # regex example: param_name=[^&]+
        return param_name + '=[^&]+'

    @staticmethod
    def not_blank_not_numeric(param_name):
        # regex example: param_name=[^&\d]+
        return param_name + '=(.*[a-zA-Z]+.*)' + Pattern.PARAM_DELIMITER  # TODO fix this regex, e.g. 1abc is not a number and still failing the validation. Fixed

    @staticmethod
    def numeric_positive(param_name):
        # regex example: param_name=(?!-)[1-9]\d*(&|$)
        return param_name + '=(?!-)[1-9]\d*' + Pattern.PARAM_DELIMITER

    @staticmethod
    def numeric(param_name):
        # regex example: param_name=(?!-)[1-9]\d*(&|$)
        return param_name + '=(-?[0-9]{0,10})' + Pattern.PARAM_DELIMITER

    @staticmethod
    def equals(param_name, param_value):
        param_value = Pattern._escape_special_characters(param_value)
        # regex example: param_name=esb\|14(&|$)
        return param_name + '=' + param_value + Pattern.PARAM_DELIMITER

    @staticmethod
    def equals_one(param_name, param_values):
        assert isinstance(param_values, list), 'param_values must be a list, otherwise use the \'equals\' method'

        param_values = Pattern._escape_special_characters(param_values)
        param_values_regex = ')|('.join(param_values)
        # regex example: param_name=((esb\|14)|(esb\|6)){1}(&|$)
        return param_name + '=(' + param_values_regex + '){1}' + Pattern.PARAM_DELIMITER

    @staticmethod
    def contains(param_name, param_value):
        # regex example: param_name=[^&]*(param_value)[^&]*
        return param_name + '=[^&]*(' + param_value + ')[^&]*'

    @staticmethod
    def contains_one(param_name, param_values):
        assert isinstance(param_values, list), 'param_values must be a list, otherwise use the \'contains\' method'
        param_values_regex = '|'.join(param_values)
        # regex example: param_name=[^&]*(param_value1|param_value2)[^&]*
        return param_name + '=[^&]*(' + param_values_regex + ')[^&]*'

    @staticmethod
    def contains_all(param_name, param_values):
        assert isinstance(param_values, list), 'param_values must be a list, otherwise use the \'contains\' method'
        param_values_regex = ')(?=.*'.join(param_values)
        # example: param_name=(?=.*param_value1)(?=.*param_value2).+
        return param_name + '=(?=.*' + param_values_regex + ').+'

    @staticmethod
    def regex(param_name, param_value):
        # regex example: param_name=esb\|14(&|$)
        return param_name + '=' + param_value + Pattern.PARAM_DELIMITER

    @staticmethod
    def _escape_special_characters(param_values):
        if isinstance(param_values, list):
            param_values = [param_value.replace('|', '\|') for param_value in param_values]  # escape | because | is a special caracter in regex
        else:
            param_values = param_values.replace('|', '\|')
        return param_values
