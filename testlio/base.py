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
        """Save TCP validation data for post processing"""

        screenshot = self.screenshot() if screenshot else None
        self.event.validate_tcp(host, uri_contains, screenshot)

    def click(self, element=None, screenshot=False, **kwargs):
        """
        Perform click on element. If element is not provided try to search
        by paramaters in kwargs.
        """

        def _click(element):
            element.click()
            self.event.click(**{'element_' + key: value for key, value in kwargs.items()})

        return self._element_action(_click, element, screenshot, **kwargs)

    def send_keys(self, data, element=None, screenshot=False, **kwargs):
        """
        Send keys to an element. If element is not provided try to search
        by paramaters in kwargs.
        """

        def _send_keys(element):
            element.send_keys(data)
            self.event.send_keys(data, **{'element_' + key: value for key, value in kwargs.items()})

        return self._element_action(_send_keys, element, screenshot, **kwargs)

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

    def _element_action(self, action, element=None, screenshot=False, **kwargs):
        """Find element and perform an action on it"""

        element = element if element else self._find_element(**kwargs)

        action(element)

        if screenshot:
            screenshot = self.screenshot()

        return element

    def _find_element(self, **kwargs):
        """
        Finds element by name or xpath if not supplied.
        Returns element and data to pass to logging.
        """

        if kwargs.has_key('name'):
            return self._find_element_by_name(kwargs['name'])
        elif kwargs.has_key('xpath'):
            return self._find_element_by_xpath(kwargs['xpath'])
        else:
            raise TypeError('Neither element `name` or `xpath` provided')

    def _find_element_by_name(self, name):
        try:
            return self.driver.find_element_by_name(name)
        except NoSuchElementException, e:
            self.event.error(element_name=name)
            raise e

    def _find_element_by_xpath(self, xpath):
        try:
            return self.driver.find_element_by_xpath(xpath)
        except NoSuchElementException, e:
            self.event.error(element_xpath=xpath)
            raise e

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
