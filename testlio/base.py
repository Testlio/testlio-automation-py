from datetime import datetime, timedelta
import os
import time
import unittest

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

from testlio.log import EventLogger


SCREENSHOTS_DIR = './screenshots'


class TestlioAutomationTest(unittest.TestCase):

    log = None
    name = None
    driver = None

    def setup_method(self, method, caps = False):
        self.name = type(self).__name__ + '.' + method.__name__
        self.event = EventLogger(self.name)

        # Setup capabilities
        capabilities = {}

        # Appium
        capabilities["appium-version"]    = os.getenv('APPIUM_VERSION')
        capabilities["name"]              = os.getenv('NAME')
        capabilities['platformName']      = os.getenv('PLATFORM')
        capabilities['platformVersion']   = os.getenv('PLATFORM_VERSION')
        capabilities['deviceName']        = os.getenv('DEVICE')
        capabilities['app']               = os.getenv('APP')
        capabilities["custom-data"]       = {'test_name': self.name}

        # Testdroid
        capabilities['testdroid_target']  = os.getenv('TESTDROID_TARGET')
        capabilities['testdroid_project'] = os.getenv('TESTDROID_PROJECT')
        capabilities['testdroid_testrun'] = os.getenv('NAME') + '-' + self.name
        capabilities['testdroid_device']  = os.getenv('TESTDROID_DEVICE')
        capabilities['testdroid_app']     = os.getenv('APP')

        # Log capabilitites before any sensitive information (credentials) are added
        # self.log({'event': {'type': 'start', 'data': capabilities}})
        self.event.start(capabilities)

        # Credentials
        capabilities['testdroid_username'] = os.getenv('USERNAME')
        capabilities['testdroid_password'] = os.getenv('PASSWORD')

        capabilities.update(caps) if caps else None

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

    def validate_tcp(self, host, from_timestamp, to_timestamp, uri_contains=None,
                     body_contains=None, screenshot=None):
        """Save TCP validation data for post processing"""

        screenshot = self.screenshot() if screenshot else None
        self.event.validate_tcp(host, from_timestamp, to_timestamp, uri_contains,
                                body_contains, screenshot)

    def click(self, element=None, screenshot=False, **kwargs):
        """
        Perform click on element. If element is not provided try to search
        by paramaters in kwargs.
        """

        def _click(element):
            element.click()
            screenshot_path = self.screenshot() if screenshot else None
            self.event.click(screenshot=screenshot_path,
                             **self._format_element_data(**kwargs))

        return self._element_action(_click, element, **kwargs)

    def send_keys(self, data, element=None, screenshot=False, **kwargs):
        """
        Send keys to an element. If element is not provided try to search
        by paramaters in kwargs.
        """

        def _send_keys(element):
            element.send_keys(data)
            screenshot_path = self.screenshot() if screenshot else None
            self.event.send_keys(data, screenshot=screenshot_path,
                                 **self._format_element_data(**kwargs))

        return self._element_action(_send_keys, element, **kwargs)

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

    def _element_action(self, action, element=None, **kwargs):
        """Find element if not supplied and send to action delegate"""

        element = element if element else self._find_element(**kwargs)
        action(element)
        return element

    def _find_element(self, **kwargs):
        """
        Finds element by name or xpath
        """

        if kwargs.has_key('name'):
            return self._find_element_by_name(kwargs['name'])
        elif kwargs.has_key('class_name'):
            return self._find_element_by_class_name(kwargs['class_name'])
        elif kwargs.has_key('id'):
            return self._find_element_by_id(kwargs['id'])
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

    def _find_element_by_class_name(self, class_name):
        try:
            return self.driver.find_element_by_class_name(class_name)
        except NoSuchElementException, e:
            self.event.error(element_name=class_name)
            raise e

    def _find_element_by_id(self, element_id):
        try:
            return self.driver.find_element_by_id(element_id)
        except NoSuchElementException, e:
            self.event.error(id=element_id)
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

        start_timestamp = datetime.utcnow()
        while True:
            if not self._alert_is_present():
                time.sleep(1.0)
                if datetime.utcnow() - start_timestamp > timedelta(seconds=timeout):
                    raise Exception("Alert didn't appear in %s seconds" % timeout)
                continue
            action()
            break

    def _format_element_data(self, **kwargs):
        """
        Formats data about the element (name, xpath) to correct form for
        EventLogger api
        """

        # Return dict of kwargs with prefix prepended to every key
        return dict(('element_' + key, value) for key, value in kwargs.items())
