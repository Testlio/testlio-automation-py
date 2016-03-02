from datetime import datetime, timedelta, time
import os
import unittest
from time import sleep

from appium import webdriver
from selenium import webdriver as seleniumdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from testlio.log import EventLogger


SCREENSHOTS_DIR = './screenshots'
DEFAULT_WAIT_TIME = 30


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
        capabilities["custom-data"]       = {'test_name': self.name}

        # if you want to use an app that's already installed on the phone...
        if os.getenv('APP'):
            capabilities['app']               = os.getenv('APP')
        else:
            capabilities['appPackage']        = os.getenv('APP_PACKAGE')
            capabilities['appActivity']       = os.getenv('APP_ACTIVITY')

        if os.getenv('NEW_COMMAND_TIMEOUT'):
            capabilities["newCommandTimeout"] = int(os.getenv('NEW_COMMAND_TIMEOUT'))
        else:
            capabilities["newCommandTimeout"] = 1300

        # Do NOT resign the app.  This is necessary for certain special app features.
        # I had to set NO_SIGN for in-app billing, otherwise I'd get the error
        # "This version of the app is not configured for billing through google play..."
        capabilities["noSign"]            = True

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

                # We've been seeing these errors lately, so here is some retry logic.
        # "Bad Request: All LGE Nexus 5 devices are busy at the moment. Please try again later."
        # i = 0
        # while True:
        #     try:
        #         self.driver = webdriver.Remote(desired_capabilities=capabilities, command_executor=os.getenv('EXECUTOR'))
        #         break
        #     except WebDriverException, e:
        #         if i < 5 and 'devices are busy' in e.msg and 'try again later' in e.msg:
        #             time.sleep(30)
        #             i += 1
        #         else:
        #             raise e

        self.driver = webdriver.Remote(desired_capabilities=capabilities, command_executor=os.getenv('EXECUTOR'))
        self.driver.implicitly_wait(130)
        
    def setup_method_selenium(self, method):
        self.name = type(self).__name__ + '.' + method.__name__
        self.event = EventLogger(self.name)
                
        # Setup capabilities
        capabilities = {}

        # Web
        capabilities['platform']  = os.getenv('PLATFORM')
        capabilities['browserName'] = os.getenv('BROWSER')
        capabilities['version'] = os.getenv('VERSION')

        self.event.start(capabilities)

        
        self.driver = seleniumdriver.Remote(
            desired_capabilities=capabilities,
            command_executor=os.getenv('EXECUTOR'))

        self.driver.implicitly_wait(DEFAULT_WAIT_TIME)

    def teardown_method(self, method):
        # self.log({'event': {'type': 'stop'}})
        self.event.stop()
        if self.driver:
            self.driver.quit()
        sleep(180)

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

    def validate_tcp(self, host, from_timestamp=None, to_timestamp=None, uri_contains=None,
                     body_contains=None, screenshot=None, request_present=None):
        """Save TCP validation data for post processing"""

        screenshot = self.screenshot() if screenshot else None
        self.event.validate_tcp(host, from_timestamp, to_timestamp, uri_contains,
                                body_contains, screenshot, request_present)

    def click(self, element=None, screenshot=False, **kwargs):
        """
        Perform click on element. If element is not provided try to search
        by paramaters in kwargs.
        """

        def _click(element):
            try:
                element.click()
                screenshot_path = self.screenshot() if screenshot else None
                self.event.click(screenshot=screenshot_path,
                                 **self._format_element_data(**kwargs))
            except:
                self.event.error()
                raise
        return self._element_action(_click, element, **kwargs)

    def send_keys(self, data, element=None, screenshot=False, **kwargs):
        """
        Send keys to an element. If element is not provided try to search
        by parameters in kwargs.
        """

        def _send_keys(element):
            try:
                element.send_keys(data)
                screenshot_path = self.screenshot() if screenshot else None
                self.event.send_keys(data, screenshot=screenshot_path,
                                     **self._format_element_data(**kwargs))
            except:
                self.event.error()
                raise
        return self._element_action(_send_keys, element, **kwargs)

    def send_text(self, data, element=None, screenshot=False, **kwargs):
        """
        Set text to an element. If element is not provided try to search
        by parameters in kwargs.
        This method is using methods provided by Appium, not native send_keys
        """

        def _send_keys(element):
            try:
                if str(os.getenv('PLATFORM')).lower() == 'android':
                    element.set_text(data)
                elif str(os.getenv('PLATFORM')).lower() == 'ios':
                    element.set_value(data.replace('\n', '', 1))
                screenshot_path = self.screenshot() if screenshot else None
                self.event.send_keys(data, screenshot=screenshot_path,
                                     **self._format_element_data(**kwargs))
            except:
                self.event.error()
                raise
        return self._element_action(_send_keys, element, **kwargs)

    def wait_and_accept_alert(self, timeout=30):
        """Wait for alert and accept"""

        def accept_alert():
            try:
                self.driver.switch_to_alert().accept()
                self.event.accept_alert()
            except:
                self.event.error()
                raise

        self._alert_action(timeout, accept_alert)

    def wait_and_dismiss_alert(self, timeout=30):
        """Wait for alert and dismiss"""

        def dismiss_alert():
            try:
                self.driver.switch_to_alert().dismiss()
                self.event.dismiss_alert()
            except:
                self.event.error()
                raise
            
        self._alert_action(timeout, dismiss_alert)

    def assertTrue(self, *args, **kwargs):
        try:
            super(TestlioAutomationTest, self).assertTrue(*args, **kwargs)
        except:
            self.event.error()
            raise

    #Message is a requirement, then the client is able to verify if we are making the right checks
    def assertEqualWithScreenShot(self, expected, actual, screenshot=False, msg=None):
        screenshot = self.screenshot() if screenshot else None
        self.event.assertion(msg, screenshot=screenshot)
        if expected != actual:
            if msg is None:
                self.assertTrue(False)
            else:
                self.assertTrue(False, msg)
            self.event.error()
        else:
            self.assertTrue(True)

    def assertTrueWithScreenShot(self, condition, screenshot=False, msg=None):
        screenshot = self.screenshot() if screenshot else None
        self.event.assertion(msg, screenshot=screenshot)
        if msg is None:
            self.assertTrue(condition)
        else:
            self.assertTrue(condition, msg)

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
        except:
            self.event.error(element_name=name)
            raise

    def _find_element_by_xpath(self, xpath):
        try:
            return self.driver.find_element_by_xpath(xpath)
        except:
            self.event.error(element_xpath=xpath)
            raise

    def _find_element_by_class_name(self, class_name):
        try:
            return self.driver.find_element_by_class_name(class_name)
        except:
            self.event.error(element_name=class_name)
            raise

    def _find_element_by_id(self, element_id):
        try:
            return self.driver.find_element_by_id(element_id)
        except:
            self.event.error(id=element_id)
            raise

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
                    raise NoSuchAlertException("Alert didn't appear in %s seconds" % timeout)
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


class NoSuchAlertException(Exception):
    pass
