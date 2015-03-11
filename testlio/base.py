from datetime import datetime, timedelta
import functools
import os
import sys
import time
import traceback
import unittest

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

from testlio.log import create_event_logger


SCREENSHOTS_DIR = './screenshots'


class TestlioAutomationTest(unittest.TestCase):

    log = None
    name = None
    driver = None

    def setup_method(self, method):
        self.name = type(self).__name__ + '.' + method.__name__
        self.event = create_event_logger(self.name)

        # Setup capabilities
        capabilities = {}

        # Appium
        capabilities["appium-version"] = os.getenv('APPIUM_VERSION')
        capabilities["name"] = os.getenv('NAME')
        capabilities['platformName'] = os.getenv('PLATFORM')
        capabilities['platformVersion'] = os.getenv('PLATFORM_VERSION')
        capabilities['deviceName'] = os.getenv('DEVICE')
        capabilities['app'] = os.getenv('APP')
        capabilities["custom-data"] = {'test_name': self.name}

        # Testdroid
        capabilities['testdroid_target'] = os.getenv('TESTDROID_TARGET')
        capabilities['testdroid_project'] = os.getenv('TESTDROID_PROJECT')
        capabilities['testdroid_testrun'] = os.getenv('NAME') + '-' + self.name
        capabilities['testdroid_device'] = os.getenv('TESTDROID_DEVICE')
        capabilities['testdroid_app'] = os.getenv('APP')

        # Log capabilitites before any sensitive information (credentials) are added
        # self.log({'event': {'type': 'start', 'data': capabilities}})
        self.event.start(capabilities)

        # Credentials
        capabilities['testdroid_username'] = os.getenv('USERNAME')
        capabilities['testdroid_password'] = os.getenv('PASSWORD')

        self.driver = webdriver.Remote(
            desired_capabilities=capabilities,
            command_executor=os.getenv('EXECUTOR'))

        self.driver.implicitly_wait(30)

    def teardown_method(self, method):
        # self.log({'event': {'type': 'stop'}})
        self.event.stop()
        if self.driver:
            self.driver.quit()

    def screenshot(self):
        """Save screenshot and return relative path"""

        time.sleep(1) # wait for animations to complete before taking a screenshot

        if not os.path.exists(SCREENSHOTS_DIR):
            os.makedirs(SCREENSHOTS_DIR)

        path = "{dir}/{name}-{time}.png".format(
            dir=SCREENSHOTS_DIR, name=self.name, time=time.mktime(time.gmtime())
        )
        self.driver.save_screenshot(path)
        return path

    def validate_tcp(self, host, uri_contains, screenshot=False):
        screenshot = self.screenshot() if screenshot else None
        self.event.validate_tcp(host, uri_contains, screenshot)

    def click(self, screenshot=False, **kwargs):

        try:
            element, element_data = self._find_element(**kwargs)
        except NoSuchElementException, e:
            self.event.error()
            raise e

        element.click()

        if screenshot:
            element_data['screenshot'] = self.screenshot()

        self.event.click(**element_data)

        return element

    def send_keys(self, data, screenshot=False, **kwargs):

        try:
            element, element_data = self._find_element(**kwargs)
        except NoSuchElementException, e:
            self.event.error()
            raise e

        element.send_keys(data)

        if screenshot:
            element_data['screenshot'] = self.screenshot()

        self.event.send_keys(data, **element_data)

        return element

    def wait_and_accept_alert(self, timeout=30):
        """Wait for alert and accept"""

        def accept_alert():
            self.driver.switch_to_alert().accept()
            self.event.accept_alert()

        self._alert_action(timeout, accept_alert)

    def wait_and_dismiss_alert(self, timeout=30):
        """Wait for alert and dismiss"""

        def dismiss_alert():
            self.driver.switch_to_alert().dismiss()
            self.event.dismiss_alert()

        self._alert_action(timeout, dismiss_alert)

    def _element_action(self, action, screenshot=False, validation=None, **kwargs):
        """Find element and perform an action on it"""

        try:
            element, element_data = self._find_element(**kwargs)
        except NoSuchElementException, e:
            self.event.error()
            raise e

        action(element)

        if screenshot:
            screenshot = self.screenshot()

        return element, element_data, screenshot

    def _find_element(self, **kwargs):
        """
        Finds element by name or xpath if not supplied.
        Returns element and data to pass to logging.
        """

        if kwargs.has_key('name'):
            element = kwargs['element'] if kwargs.has_key('element')\
                      else self.driver.find_element_by_name(kwargs['name'])
            element_data = {'element_name': kwargs['name']}
        elif kwargs.has_key('xpath'):
            element = kwargs['element'] if kwargs.has_key('element')\
                      else self.driver.find_element_by_xpath(kwargs['xpath'])
            element_data = {'element_xpath': kwargs['xpath']}
        else:
            raise TypeError('Name or xpath of element not defined')

        return element, element_data

    def _alert_is_present(self):
        """Check if alert message is present"""

        try:
            self.driver.switch_to_alert().text
            return True
        except Exception, e:
            return False

    def _alert_action(self, timeout, action):
        """Wait for alert and perform action"""

        start_timestamp = datetime.now()
        while True:
            if not self._alert_is_present():
                time.sleep(1.0)
                if datetime.now() - start_timestamp > timedelta(seconds=timeout):
                    raise Exception("Alert didn't appear in %s seconds" % timeout)
                continue
            action()
            break
