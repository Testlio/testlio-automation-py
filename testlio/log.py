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
    def get_logger_testlio(cls, name):
        if not os.path.exists(DIR):
            os.makedirs(DIR)
        if not cls.loggers.has_key(name):

            # Calculate the log file name
            file_name = '.'.join(name.split('.')[1:]) if len(name.split('.')) > 2 else name

            cls.loggers[name] = configure_logger(
                logging.getLogger('{base}.{name}'.format(base=BASE, name=name)),
                logging.Formatter('%(message)s'),
                logging.FileHandler('{dir}/{name}.log'.format(dir=DIR, name=file_name)))
        return cls.loggers[name]

    @classmethod
    def get_logger_calabash(cls, name):
        if not os.path.exists(DIR):
            os.makedirs(DIR)
        if not cls.loggers.has_key(name):

            cls.loggers[name] = configure_logger(
                logging.getLogger('{base}.{name}'.format(base=BASE, name=name)),
                logging.Formatter('\t\t%(message)s'),
                logging.FileHandler('calabash.log'))

        return cls.loggers[name]

    def __init__(self, name, hosting_platform, test_file_dir=None, test_file_name=None):
        super(EventLogger, self).__init__()

        self.hosting_platform = hosting_platform

        if self.hosting_platform == 'testdroid':
            ndx = str.index(name, '.')
            class_name = name[:ndx]
            script_name = name[ndx+1:]

            main_file_name = 'calabash.log'
            main_file = open(main_file_name, 'a')

            # Should look like:
            # Feature: tests.test_script_a.TestClassA
            main_file.write("\nFeature: %s.%s.%s\n\n" % (test_file_dir, test_file_name, class_name))
            main_file.write("    Scenario: %s                                             # features/my_first.feature:3\n\n" % script_name)

            self._logger = EventLogger.get_logger_calabash(name)
        else:
            self._logger = EventLogger.get_logger_testlio(name)

    def start(self, data=None):
        """Log start event"""

        self._log_info(self._event_data('start', data))

    def stop(self):
        """Log stop event"""

        self._log_info(self._event_data('stop'))

    def assertion(self, data=None, **kwargs):
        """Log assert event"""

        self._log_info(self._event_data('assert', data, **kwargs))

    def click(self, data=None, **kwargs):
        """Log element click event"""

        self._log_info(self._event_data('click', data, **kwargs))

    def find(self, **kwargs):
        """Log element find event"""

        self._log_info(self._event_data('find', **kwargs))

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

    def validate_tcp(self, host, from_timestamp=None, to_timestamp=None, uri_contains=None,
                     body_contains=None, screenshot=None, request_present=None):
        """Log TCP validation event for post processing"""

        data = {
            'timestamps': {},
            'tcpdump': {
                'host': host
            }
        }

        if from_timestamp:
            data['timestamps']['from'] = from_timestamp.isoformat()
        if to_timestamp:
            data['timestamps']['to'] = to_timestamp.isoformat()
        if uri_contains:
            data['tcpdump']['uri_contains'] = uri_contains
        if body_contains:
            data['tcpdump']['body_contains'] = body_contains
        # validate, that requests are not sent in this timewindow
        if request_present != None:
            data['tcpdump']['request_present'] = request_present

        self._log_info(self._validation_data(data, screenshot))

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

    def _format_dict_data(self, data):
        out_str = ''
        out_str += data.get('timestamp') + ' - '

        # screenshot has no event data
        event_data = data.get('event')
        if event_data:
            out_str += event_data.get('type') + ' "'

            element_data = data.get('element')
            if element_data:
                out_str += str(element_data) + ' "'

            data_data = data.get('event').get('data')
            if data_data:
                out_str += str(data_data) + '"'

        ss_str = data.get('screenshot')
        if ss_str:
            ss_str = ss_str.split('/')[-1]
            out_str += ' - ' + ss_str

        return out_str

    def _log_info(self, data):
        if self.hosting_platform == 'testdroid':
            try:
                data['timestamp'] = datetime.datetime.utcnow().strftime('%H:%M:%S')
                self._logger.info("Then " + self._format_dict_data(data) + "                                     # features/step_definitions/calabash_steps.rb")
            except Exception, e:
                self._logger.info("unhandled case in logger:")
                self._logger.info(str(e))
                self._logger.info(str(data))
            if 'screenshot' in data:
                self._logger.info('- java -jar /usr/local/rvm/gems/ruby-2.1.2@global/gems/calabash-android-0.5.14/lib/calabash-android/lib/screenshotTaker.jar "04135148006060008790" "%s"' % data['screenshot'])
        else:
            data['timestamp'] = datetime.datetime.utcnow().isoformat()
            self._logger.info(json.dumps(data))

    def _log_error(self, data):
        if self.hosting_platform == 'testdroid':
            try:
                data['timestamp'] = datetime.datetime.utcnow().strftime('%H:%M:%S')
                self._logger.error("Step unsuccessful: " + self._format_dict_data(data) + "                                     # features/step_definitions/calabash_steps.rb")
            except Exception, e:
                self._logger.error("unhandled case in logger:")
                self._logger.error(str(e))
                self._logger.error(str(data))
            if 'screenshot' in data:
                self._logger.info('- java -jar /usr/local/rvm/gems/ruby-2.1.2@global/gems/calabash-android-0.5.14/lib/calabash-android/lib/screenshotTaker.jar "04135148006060008790" "%s"' % data['screenshot'])
        else:
            data['timestamp'] = datetime.datetime.utcnow().isoformat()
            self._logger.error(json.dumps(data))

