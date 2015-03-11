import datetime
import json
import logging
import os
import sys
import traceback


BASE = 'testlio.automation'
DIR = './logs'

# Set up base logger
logger = logging.getLogger(BASE)
logger.setLevel(logging.DEBUG)

console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_formatter = logging.Formatter('%(message)s')

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(console_formatter)
logger.addHandler(handler)


if not os.path.isdir(DIR):
    os.mkdir(DIR)


def create_event_logger(name):
    logger = logging.getLogger('{base}.{name}'.format(base=BASE, name=name))
    handler = logging.FileHandler('{dir}/{name}.log'.format(dir=DIR, name=name))
    handler.setFormatter(file_formatter)
    logger.addHandler(handler)
    return EventLogger(logger)


class EventLogger(object):
    """Logging Testlio automation events"""

    def __init__(self, logger):
        super(EventLogger, self).__init__()
        self._logger = logger

    def start(self, data=None):
        """Log start event"""

        self._log_info(self._event_data('start', data))

    def stop(self):
        """Log stop event"""

        self._log_info(self._event_data('stop'))

    def click(self, **kwargs):
        """Log element click event"""

        self._log_info(self._event_data('click', **kwargs))

    def send_keys(self, data, **kwargs):
        """Log element send_keys event"""

        self._log_info(self._event_data('send_keys', data, **kwargs))

    def accept_alert(self):
        self._log_info(self._event_data('accept_alert'))

    def dismiss_alert(self):
        self._log_info(self._event_data('dismiss_alert'))

    def screenshot(self, path):
        """Log screenshot event"""

        self._log_info({'screenshot': path})

    def validate_tcp(self, host, uri_contains, screenshot=None):
        """Log TCP validation event for post processing"""

        self._log_info(
            self._validation_data({
                'tcpdump': {
                    'host': host, 'uri_contains': uri_contains
                }
            },
            screenshot)
        )

    def error(self, **kwargs):
        """Log exception"""

        data = {}

        element_data = self._element_data(**kwargs)
        if element_data:
            data['element'] = element_data

        exc_info = sys.exc_info()
        data['error'] = {
            'message': traceback.format_exception_only(exc_info[0], exc_info[1])[0],
            'trace': traceback.format_exc(exc_info[2])
        }
        self._log_error(data)

    def _validation_data(self, data, screenshot=None):
        """Create validation event data"""

        return self._event_data('validation', data, screenshot=screenshot)

    def _event_data(self, event_type, event_data=None, **kwargs):
        """Create event data based on args"""

        data = {
            'event': {
                'type': event_type
            }
        }

        element_data = self._element_data(**kwargs)
        if element_data:
            data['element'] = element_data
        if event_data != None:
            data['event']['data'] = event_data
        if kwargs.has_key('screenshot') and kwargs['screenshot']:
            data['screenshot'] = kwargs['screenshot']

        return data

    def _element_data(self, **kwargs):
        """Create element data dict based on kwargs"""

        prefix = 'element_'
        data = {}

        for key, value in kwargs.items():
            if not key.startswith(prefix):
                continue
            data[''.join(key.split('_')[1:])] = value

        return data

    def _log_info(self, data):
        self._log(self._logger.info, data)

    def _log_error(self, data):
        self._log(self._logger.error, data)

    def _log(self, log, data):
        data['timestamp'] = datetime.datetime.now().isoformat()
        log(json.dumps(data))
