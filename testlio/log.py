import datetime
import json
import logging
import os
import sys
import traceback


BASE = 'testlio.automation'
DIR = './logs'


def configure_logger(logger, formatter, handler, level=logging.DEBUG):
    logger.setLevel(level)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class EventLogger(object):
    """Logging Testlio automation events"""

    # Keep track of loggers created so not to configure twice
    loggers = {}

    # Configure base logger once
    base_logger = configure_logger(
        logging.getLogger(BASE),
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        logging.StreamHandler())

    @classmethod
    def get_logger(cls, name):
        if not cls.loggers.has_key(name):
            cls.loggers[name] = configure_logger(
                logging.getLogger('{base}.{name}'.format(base=BASE, name=name)),
                logging.Formatter('%(message)s'),
                logging.FileHandler('{dir}/{name}.log'.format(dir=DIR, name=name)))
        return cls.loggers[name]

    def __init__(self, name):
        super(EventLogger, self).__init__()
        print name
        self._logger = EventLogger.get_logger(name)
        print self._logger

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
        """
        Extract data from kwargs that are about elements to log
        """

        prefix = 'element_'
        data = {}

        for key, value in kwargs.items():
            if not key.startswith(prefix):
                continue
            # Remove prefix from key and add to data
            data[''.join(key.split('_')[1:])] = value

        return data

    def _log_info(self, data):
        self._log(self._logger.info, data)

    def _log_error(self, data):
        self._log(self._logger.error, data)

    def _log(self, log, data):
        data['timestamp'] = datetime.datetime.now().isoformat()
        log(json.dumps(data))
