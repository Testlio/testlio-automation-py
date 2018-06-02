import os
import re
import threading
import time
import unittest
from datetime import datetime, timedelta
from time import sleep, time

from appium import webdriver
from appium.webdriver.common.touch_action import TouchAction
from selenium import webdriver as seleniumdriver
from selenium.common.exceptions import *
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    # for backwards compatibility (running on Testlio's site)
    from testlio.log import EventLogger
except ImportError:
    from log import EventLogger

SCREENSHOTS_DIR = './screenshots'
DEFAULT_WAIT_TIME = 20
SOFT_ASSERTIONS_FAILURES = "SOFT_ASSERTIONS_FAILURES"
HASHED_VALUES = "HASHED_VALUES"
FAILURES_FOUND = "FAILURES_FOUND"


class TestlioAutomationTest(unittest.TestCase):
    log = None
    name = None
    driver = None
    angel_driver = None
    caps = {}
    default_implicit_wait = 10
    IS_IOS = False
    IS_ANDROID = False
    capabilities = {}
    passed = False

    def parse_test_script_dir_and_filename(self, filename):
        # used in each test script to get its own path
        pth = os.path.dirname(os.path.abspath(filename))
        pth = os.path.basename(os.path.normpath(pth))
        ndx = str.index(filename, '.py')
        filename = filename[:ndx]
        filename = filename.split('/')[-1]
        return pth, filename

    @classmethod
    def setUpClass(cls):
        platform = os.getenv('PLATFORM') or (
            'android' if os.getenv('ANDROID_HOME') else 'ios')
        if platform == 'ios' and 'TESTDROID_SERVER_URL' in os.environ or 'VIRTUAL_ENV' in os.environ:
            cls.capabilities['platformName'] = os.getenv('PLATFORM') or (
                'android' if os.getenv('ANDROID_HOME') else 'ios')
            cls.capabilities['deviceName'] = os.getenv('DEVICE') or os.getenv('DEVICE_DISPLAY_NAME')
            cls.capabilities['app'] = os.getenv('APP') or os.getenv('APPIUM_APPFILE')
            cls.capabilities['newCommandTimeout'] = os.getenv('NEW_COMMAND_TIMEOUT')

            if os.getenv('BROWSER'):      # mobile web support
                cls.capabilities['browserName'] = os.getenv('BROWSER')
            if os.getenv('FULL_RESET'):
                cls.capabilities['fullReset'] = os.getenv('FULL_RESET', True)
            if os.getenv('FAST_RESET'):
                cls.capabilities['fastReset'] = os.getenv('FAST_RESET')

            # iOS 10, XCode8 support
            if os.getenv('AUTOMATION_NAME'):
                cls.capabilities["automationName"] = os.getenv('AUTOMATION_NAME')
            if os.getenv('UDID'):
                cls.capabilities["udid"] = os.getenv('UDID')

            executor = os.getenv('EXECUTOR', 'http://localhost:4723/wd/hub')

            try:
                print "Start dummy Appium session"
                cls.driver = webdriver.Remote(
                    desired_capabilities=cls.capabilities,
                    command_executor=executor)

                cls.driver.implicitly_wait(10)

                cls.driver.quit()
            except:
                print "Finish dummy Appium session"
                pass

    def setup_method(self, method, caps=False):
        self.name = type(self).__name__ + '.' + method.__name__

        if 'TESTDROID_SERVER_URL' in os.environ or 'VIRTUAL_ENV' in os.environ:

            try:
                self.test_script_filename
            except AttributeError:
                err = "you need the line 'test_script_filename = __file__' after your class declaration and before \
                your first test method in each of your test script files"
                print err
                raise RuntimeError(err)

            test_script_dir, test_script_filename = self.parse_test_script_dir_and_filename(self.test_script_filename)
            self.hosting_platform = 'testdroid'
            self.event = EventLogger(self.name,
                                     hosting_platform=self.hosting_platform,
                                     test_file_dir=test_script_dir,
                                     test_file_name=test_script_filename)

            self.capabilities['platformName'] = os.getenv('PLATFORM') or (
                'android' if os.getenv('ANDROID_HOME') else 'ios')
            self.capabilities['deviceName'] = os.getenv('DEVICE') or os.getenv('DEVICE_DISPLAY_NAME')
            self.capabilities['app'] = os.getenv('APP') or os.getenv('APPIUM_APPFILE')
            self.capabilities['newCommandTimeout'] = os.getenv('NEW_COMMAND_TIMEOUT')

            # iOS 10, XCode8 support
            if os.getenv('AUTOMATION_NAME'):
                self.capabilities["automationName"] = os.getenv('AUTOMATION_NAME')
            if os.getenv('UDID'):
                self.capabilities["udid"] = os.getenv('UDID')

            executor = os.getenv('EXECUTOR', 'http://localhost:4723/wd/hub')

        else:  # we're running on Testlio
            self.hosting_platform = 'testlio'
            self.event = EventLogger(self.name,
                                     hosting_platform=self.hosting_platform)

            self.capabilities["name"] = os.getenv('NAME')
            self.capabilities['platformName'] = os.getenv('PLATFORM')
            self.capabilities['platformVersion'] = os.getenv('PLATFORM_VERSION')
            self.capabilities['udid'] = os.getenv('UDID')
            self.capabilities['deviceName'] = os.getenv('DEVICE')
            self.capabilities["custom-data"] = {'test_name': self.name}

            executor = os.getenv('EXECUTOR')

        # if you want to use an app that's already installed on the phone...
        if os.getenv('APP'):
            self.capabilities['app'] = os.getenv('APP')
        else:
            self.capabilities['appPackage'] = os.getenv('APP_PACKAGE')
            self.capabilities['appActivity'] = os.getenv('APP_ACTIVITY')

        if os.getenv('NEW_COMMAND_TIMEOUT'):
            self.capabilities["newCommandTimeout"] = os.getenv('NEW_COMMAND_TIMEOUT')
        else:
            self.capabilities["newCommandTimeout"] = 1300

        # Do NOT resign the app.  This is necessary for certain special app features.
        # I had to set NO_SIGN for in-app billing, otherwise I'd get the error
        # "This version of the app is not configured for billing through google play..."
        self.capabilities["noSign"] = True

        # Testdroid
        if os.getenv('TESTDROID_TARGET'):
            self.capabilities['testdroid_target'] = os.getenv('TESTDROID_TARGET')

        if os.getenv('TESTDROID_PROJECT'):
            self.capabilities['testdroid_project'] = os.getenv('TESTDROID_PROJECT')

        if os.getenv('NAME'):
            self.capabilities['testdroid_testrun'] = os.getenv('NAME') + '-' + self.name

        if os.getenv('TESTDROID_DEVICE'):
            self.capabilities['testdroid_device'] = os.getenv('TESTDROID_DEVICE')

        # Log capabilitites before any sensitive information (credentials) are added
        # self.log({'event': {'type': 'start', 'data': self.capabilities}})
        if self.hosting_platform == 'testlio':
            self.event.start(self.capabilities)

        # if 'iPad' in self.driver.capabilities['deviceName']:
        self.capabilities['useJSONSource'] = 'false' # uncomment after the bug on webDriver is fixed
        self.capabilities['performNativeValidation'] = 'false'

        self.capabilities.update(caps) if caps else None

        self.driver = webdriver.Remote(
            desired_capabilities=self.capabilities,
            command_executor=executor)

        self.driver.implicitly_wait(self.default_implicit_wait)

        if str(self.capabilities['platformName']).lower() == 'android':
            self.IS_ANDROID = True
            self.IS_IOS = False
        elif str(self.capabilities['platformName']).lower() == 'ios':
            self.IS_ANDROID = False
            self.IS_IOS = True

        os.environ[FAILURES_FOUND] = "false"
        os.environ[SOFT_ASSERTIONS_FAILURES] = ""
        os.environ[HASHED_VALUES] = ""
        self.caps = self.capabilities

        self.angel_driver = self.driver
        try:
            self.angel_driver.implicitly_wait(10)
        except:
            pass

    def setup_method_selenium(self, method):
        self.name = type(self).__name__ + '.' + method.__name__
        self.event = EventLogger(self.name)

        # Setup self.capabilities
        capabilities = {}

        # Web
        capabilities['platform'] = os.getenv('PLATFORM')
        capabilities['browserName'] = os.getenv('BROWSER')
        capabilities['version'] = os.getenv('VERSION')

        self.event.start(capabilities)

        self.driver = seleniumdriver.Remote(
            desired_capabilities=self.capabilities,
            command_executor=os.getenv('EXECUTOR'))

        self.driver.implicitly_wait(DEFAULT_WAIT_TIME)
        self.caps = self.capabilities

    def teardown_method(self, method):
        # self.log({'event': {'type': 'stop'}})
        self.event.stop()
        if self.driver:
            try:
                self.driver.quit()
            except:
                self.event._log_info(self.event._event_data("Failure during closing the driver"))
        if os.environ[FAILURES_FOUND] == "true" and self.passed:
            os.environ[FAILURES_FOUND] = "false"
            self.event._log_info(
                self.event._event_data("Soft failures found. Failures are: " + os.environ[SOFT_ASSERTIONS_FAILURES]))
            self.fail(msg="Soft failures found. Failures are: " + os.environ[SOFT_ASSERTIONS_FAILURES])

    def get_clickable_element(self, **kwargs):
        # self.dismiss_update_popup()
        self.set_implicit_wait(1)
        if kwargs.has_key('timeout'):
            timeout = kwargs['timeout']
        else:
            timeout = 10
        wait = WebDriverWait(self.driver, timeout, poll_frequency=0.5,
                             ignored_exceptions=[ElementNotVisibleException, ElementNotSelectableException,
                                                 StaleElementReferenceException, TimeoutException])
        try:
            if kwargs.has_key('name'):
                return wait.until(EC.element_to_be_clickable((By.XPATH,
                                                              '//*[contains(translate(@text,"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),"{0}") or contains(translate(@content-desc,"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),"{0}")]'.format(
                                                                  str(kwargs['name']).lower()))))
            elif kwargs.has_key('class_name'):
                return wait.until(EC.element_to_be_clickable((By.CLASS_NAME, kwargs['class_name'])))
            elif kwargs.has_key('id'):
                return wait.until(EC.element_to_be_clickable((By.ID, kwargs['id'])))
            elif kwargs.has_key('accessibility_id'):
                return wait.until(EC.element_to_be_clickable((By.ID, kwargs['accessibility_id'])))
            elif kwargs.has_key('xpath'):
                return wait.until(EC.element_to_be_clickable((By.XPATH, kwargs['xpath'])))
            else:
                raise TypeError('Element is not found')
        except:
            return False

    def get_element(self, **kwargs):
        # self.dismiss_update_popup()
        #self.run_phantom_driver_click('Search')
        self.set_implicit_wait(1)
        if kwargs.has_key('timeout'):
            timeout = kwargs['timeout']
        else:
            timeout = 10
        wait = WebDriverWait(self.driver, timeout, poll_frequency=0.5,
                             ignored_exceptions=[ElementNotVisibleException, ElementNotSelectableException,
                                                 StaleElementReferenceException, TimeoutException, WebDriverException])
        try:
            if kwargs.has_key('name'):
                return wait.until(EC.presence_of_element_located((By.XPATH,
                                                                  '//*[contains(translate(@text,"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),"{0}") or contains(translate(@content-desc,"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),"{0}")]'.format(
                                                                      str(kwargs['name']).lower()))))
            elif kwargs.has_key('class_name'):
                return wait.until(EC.presence_of_element_located((By.CLASS_NAME, kwargs['class_name'])))
            elif kwargs.has_key('id'):
                return wait.until(EC.presence_of_element_located((By.ID, kwargs['id'])))
            elif kwargs.has_key('accessibility_id'):
                return wait.until(EC.presence_of_element_located((By.ACCESSIBILITY_ID, kwargs['accessibility_id'])))
            elif kwargs.has_key('xpath'):
                return wait.until(EC.presence_of_element_located((By.XPATH, kwargs['xpath'])))
            else:
                raise TypeError('Element is not found')
        except:
            return False

    def get_visible_element(self, **kwargs):
        # self.dismiss_update_popup()
        self.set_implicit_wait(1)
        if kwargs.has_key('timeout'):
            timeout = kwargs['timeout']
        else:
            timeout = 10
        wait = WebDriverWait(self.driver, timeout, poll_frequency=0.5,
                             ignored_exceptions=[ElementNotVisibleException, ElementNotSelectableException,
                                                 StaleElementReferenceException, TimeoutException, WebDriverException])
        try:
            if kwargs.has_key('name'):
                return wait.until(EC.visibility_of_element_located((By.XPATH,
                                                                    '//*[contains(translate(@text,"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),"{0}") or contains(translate(@content-desc,"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),"{0}")]'.format(
                                                                        str(kwargs['name']).lower()))))
            elif kwargs.has_key('class_name'):
                return wait.until(EC.visibility_of_element_located((By.CLASS_NAME, kwargs['class_name'])))
            elif kwargs.has_key('id'):
                return wait.until(EC.visibility_of_element_located((By.ID, kwargs['id'])))
            elif kwargs.has_key('accessibility_id'):
                return wait.until(EC.visibility_of_element_located((By.ID, kwargs['accessibility_id'])))
            elif kwargs.has_key('xpath'):
                return wait.until(EC.visibility_of_element_located((By.XPATH, kwargs['xpath'])))
            else:
                raise TypeError('Element is not found')
        except:
            return False

    def get_elements(self, **kwargs):
        # self.dismiss_update_popup()
        self.set_implicit_wait(1)
        if kwargs.has_key('timeout'):
            timeout = kwargs['timeout']
        else:
            timeout = 10
        wait = WebDriverWait(self.driver, timeout, poll_frequency=0.5,
                             ignored_exceptions=[ElementNotVisibleException, ElementNotSelectableException,
                                                 StaleElementReferenceException, TimeoutException, WebDriverException])
        try:
            if kwargs.has_key('name'):
                return wait.until(EC.presence_of_all_elements_located((By.XPATH,
                                                                       '//*[contains(translate(@text,"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),"{0}") or contains(translate(@content-desc,"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),"{0}")]'.format(
                                                                           str(kwargs['name']).lower()))))
            elif kwargs.has_key('class_name'):
                return wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, kwargs['class_name'])))
            elif kwargs.has_key('id'):
                return wait.until(EC.presence_of_all_elements_located((By.ID, kwargs['id'])))
            elif kwargs.has_key('accessibility_id'):
                return wait.until(EC.presence_of_all_elements_located((By.ID, kwargs['accessibility_id'])))
            elif kwargs.has_key('xpath'):
                return wait.until(EC.presence_of_all_elements_located((By.XPATH, kwargs['xpath'])))
            else:
                raise TypeError('Elements are not found')
        except:
            return []

    def is_element_on_screen_area(self, element):
        if element:
            element_x = element.location['x']
            element_y = element.location['y']

            element_w = element.size['width']
            element_h = element.size['height']

            display_w = self.driver.get_window_size()['width']
            display_h = self.driver.get_window_size()['height']

            return (element_x > 0 and ((element_x + element_w) <= display_w)) and (
                    element_y > 0 and ((element_y + element_h) <= display_h))
        return False

    def is_element_visible(self, element):
        if element:
            if self.IS_IOS:
                return (element.location['x'] > 0 or element.location['y'] > 0) and element.is_displayed()
            else:
                return element.is_displayed()
        return False

    def dismiss_update_popup(self):
        try:
            if "update your os" in str(self.driver.page_source).lower():
                self.driver.back()
        except:
            pass

    def set_implicit_wait(self, wait_time=-1):
        """
        Wrapper that sets implicit wait, defaults to self.default_implicit_wait
        """
        if wait_time == -1:
            wait_time = self.default_implicit_wait

        try:
            self.driver.implicitly_wait(wait_time)
        except:
            pass

    def screenshot(self):
        import time
        import subprocess
        if str(self.capabilities['platformName']).lower() == 'ios':
            time.sleep(1)  # wait for animations to complete before taking a screenshot

            try:
                path = "{dir}/{name}-{time}.png".format(dir=SCREENSHOTS_DIR, name=self.name,
                                                        time=time.mktime(time.gmtime()))

                if not os.environ['IOS_UDID'] and not os.environ['UDID']:
                    raise Exception('screenshot failed. IOS_UDID not provided')

                if os.environ['IOS_UDID']:
                    subprocess.call("echo $IOS_UDID &> consoleoutput.txt", shell=True)
                    subprocess.call("idevicescreenshot -u $IOS_UDID \"" + path + "\" &> consoleoutput2.txt", shell=True)
                else:
                    subprocess.call("echo $UDID &> consoleoutput.txt", shell=True)
                    subprocess.call("idevicescreenshot -u $UDID \"" + path + "\" &> consoleoutput2.txt", shell=True)

                return path
            except:
                return False
        elif str(self.capabilities['platformName']).lower() == 'android':
            time.sleep(1)  # wait for animations to complete before taking a screenshot

            if not os.path.exists(SCREENSHOTS_DIR):
                os.makedirs(SCREENSHOTS_DIR)

            path = "{dir}/{name}-{time}.png".format(
                dir=SCREENSHOTS_DIR, name=self.name, time=time.mktime(time.gmtime())
            )
            try:
                self.driver.save_screenshot(path)
                return path
            except:
                subprocess.call("adb shell screencap -p | perl -pe 's/\x0D\x0A/\x0A/g' > " + path, shell=True)
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
        self.run_phantom_driver_click('Search')
        sleep(2)

        def _click(element):
            try:
                if element:
                    try:
                        if self.uiautomator2:
                            readable_name = element.text or \
                                            element.get_attribute('name') or \
                                            element.get_attribute('resourceId') or \
                                            element.get_attribute('contentDescription') or \
                                            element.get_attribute('value') or \
                                            element.tag_name      
                        else:
                            readable_name = element.text or \
                                        element.get_attribute('name') or \
                                        element.get_attribute('resource-id') or \
                                        element.get_attribute('content-desc') or \
                                        element.get_attribute('value') or \
                                        element.tag_name
                        kwargs['Element'] = str(readable_name).replace(": u'", ": '")
                    except:
                        pass
                    element.click()
                else:
                    # self.event._log_info(self.event._event_data("*** WARNING ***  Element is absent"))
                    self.event.error()
                screenshot_path = self.screenshot() if screenshot else None
                self.event.click(screenshot=screenshot_path,
                                 **self._format_element_data(**kwargs))
            except:
                self.event.error()
                self.assertTrueWithScreenShot(False, screenshot=True, msg="The element with args '{0}' or {1} cannot be found during Click method".format(str(kwargs), str(element)))

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
                self.assertTrueWithScreenShot(False, screenshot=True, msg="The element with args '{0}' or {1} cannot be found during Send Keys method".format(str(kwargs), str(element)))

        return self._element_action(_send_keys, element, **kwargs)

    def send_text(self, data, element=None, screenshot=False, **kwargs):
        """
        Set text to an element. If element is not provided try to search
        by parameters in kwargs.
        This method is using methods provided by Appium, not native send_keys
        """

        def _send_keys(element):
            try:
                if str(self.caps['platformName']).lower() == 'android':
                    element.send_text(data)
                elif str(self.caps['platformName']).lower() == 'ios':
                    element.set_value(data.replace('\n', '', 1))
                screenshot_path = self.screenshot() if screenshot else None
                self.event.send_keys(data, screenshot=screenshot_path,
                                     **self._format_element_data(**kwargs))
            except:
                self.event.error()
                self.assertTrueWithScreenShot(False, screenshot=True, msg="The element with args '{0}' or {1} cannot be found during Send Text method".format(str(kwargs), str(element)))

        return self._element_action(_send_keys, element, **kwargs)

    def wait_and_accept_alert(self, timeout=20):
        """Wait for alert and accept"""

        def accept_alert():
            try:
                self.driver.switch_to_alert().accept()
                self.event.accept_alert()
            except:
                self.event.error()
                raise

        self._alert_action(timeout, accept_alert)

    def wait_and_dismiss_alert(self, timeout=20):
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

    # Message is a requirement, then the client is able to verify if we are making the right checks
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

    def exists(self, **kwargs):
        """
        Finds element by name or xpath
        advanced:
            call using an element:
            my_layout = self.get_element(class_name='android.widget.LinearLayout')
            self.exists(name='Submit', driver=my_layout)
        """
        self.run_phantom_driver_click('Search')
        if kwargs.has_key('element'):
            try:
                return kwargs['element']
            except:
                return False
        else:
            try:
                return self.get_element(**kwargs)
            except NoSuchElementException:
                return False
                # finally:
                #     self.driver.implicitly_wait(self.default_implicit_wait)

    def not_exists(self, **kwargs):
        """
        Waits until element does not exist.  Waits up to <implicit_wait> seconds.
        Optional parameter: timeout=3 if you only want to wait 3 seconds.  Default=30
        Return: True or False
        """
        if 'timeout' in kwargs:
            timeout = (kwargs['timeout'])
        else:
            timeout = 30

        start_time = time()

        kwargs['timeout'] = 0  # we want exists to return immediately
        while True:
            elem = self.exists(**kwargs)
            if not elem:
                return True

            if time() - start_time > timeout:
                return False

    """
    The method works only with (name|value) and (text|content-desc) attributes
    Params:
     - list_of_text_keys - the list of the keywords (Names, Values, Text, Content-Desc)
     - case_sensitive - skip the case
     - strict_visibility - sometimes the element could be visible on the screen and have the visibility=False
     - strict - if we want to stop the tests after the first failed validation
     - screenshot - take the screenshot or no
     - with_timeout - set the timeout before the getting of the page source
    """

    def verify_in_batch(self, data, case_sensitive=True, strict_visibility=True, screenshot=True, strict=False,
                        with_timeout=2):
        sleep(with_timeout)

        self.event.assertion(data="*** BATCH VERIFICATION START ***", screenshot=self.screenshot())

        self.run_phantom_driver_click('Search')

        if 'iPad' in self.capabilities['deviceName']:
            if strict:
                if type(data) is list:
                    for key in data:
                        self.assertTrueWithScreenShot(self.exists(id=key, timeout=7) or self.exists(accessibility_id=key, timeout=7), screenshot=False,
                                                      msg="Element '%s' is expected to be existed on the page" % key)
                else:
                    self.assertTrueWithScreenShot(self.exists(id=data) or self.exists(accessibility_id=data), screenshot=False,
                                                  msg="Element '%s' is expected to be existed on the page" % data)
            else:
                if type(data) is list:
                    if self.__hash_validations(data):
                        self._validate_batch(data, strict, strict_visibility)

                else:
                    if not (self.exists(id=data, timeout=7) or self.exists(accessibility_id=data, timeout=7)):
                        self.__log_batch_error(data)
        else:
            self._validate_batch(data, strict, strict_visibility)

        self.event.assertion(data="*** BATCH VERIFICATION END ***")

    def _validate_batch(self, data, strict, strict_visibility):
        try:
            page_source = self.driver.page_source.encode('utf-8')
        except:
            page_source = self.driver.page_source.encode('ascii', 'ignore').decode('ascii')
        error_flag = False
        pattern = '^\s+<XCUIElementType.*(name|value)=\"{0}\".*visible=\"true\".*/>$'
        if not strict_visibility:
            pattern = '^\s+<XCUIElementType.*(name|value)=\"{0}\".*/>$'
        if str(self.capabilities['platformName']).lower() == 'android':
            pattern = '{0}'
        if type(data) is list:
            for key in data:
                if strict:
                    self.assertTrueWithScreenShot(re.search(
                        r'{0}'.format(pattern.format(key)), page_source, re.M | re.I), screenshot=False,
                        msg="Element '%s' is expected to be existed on the page" % key)
                else:
                    if not re.search(r'{0}'.format(pattern.format(key)), page_source, re.M | re.I):
                        error_flag = self.__log_batch_error(key)
                    else:
                        self.event._log_info(self.event._event_data("*** SUCCESS *** Element is presented: '%s'" % key))
        else:
            if strict:
                self.assertTrueWithScreenShot(re.search(
                    r'{0}'.format(pattern.format(data)), page_source, re.M | re.I), screenshot=False,
                    msg="Element '%s' is expected to be existed on the page" % data)
            else:
                if not re.search(r'{0}'.format(pattern.format(data)), page_source, re.M | re.I):
                    error_flag = self.__log_batch_error(data)
                else:
                    self.event._log_info(self.event._event_data("*** SUCCESS *** Element is presented: '%s'" % data))

        if error_flag:
            self._page_source_to_console_log(page_source)

    def __hash_validations(self, list):
        val = hash(str(list))
        hashlist = os.environ[HASHED_VALUES]

        if str(val) not in hashlist:
            hashlist += str(val) + ' '
            os.environ[HASHED_VALUES] = hashlist
            return False
        else:
            return True

    def __log_batch_error(self, data):
        errors = os.environ[SOFT_ASSERTIONS_FAILURES]
        self.event.assertion(data="*** FAILURE *** Element is missing: '%s'" % data)
        errors += "\nElement is missing: '%s'" % data
        os.environ[SOFT_ASSERTIONS_FAILURES] = errors
        os.environ[FAILURES_FOUND] = "true"
        return True

    def exists_in_page_source(self, data):
        if data not in self.driver.page_source:
            errors = os.environ[SOFT_ASSERTIONS_FAILURES]

            self.event.assertion(data="*** FAILURE *** Element is missing: '%s'" % data)

            errors += "\nElement is missing: '%s'" % data
            os.environ[SOFT_ASSERTIONS_FAILURES] = errors

    def verify_exists(self, strict=False, **kwargs):
        screenshot = False
        if kwargs.has_key('screenshot') and kwargs['screenshot']:
            screenshot = True

        if kwargs.has_key('readable_name'):
            selector = kwargs['readable_name']
        elif kwargs.has_key('name'):
            selector = kwargs['name']
        elif kwargs.has_key('accessibility_id'):
            selector = kwargs['accessibility_id']
        elif kwargs.has_key('class_name'):
            selector = kwargs['class_name']
        elif kwargs.has_key('id'):
            selector = kwargs['id']
        elif kwargs.has_key('xpath'):
            selector = kwargs['xpath']
        elif kwargs.has_key('element'):
            selector = str(kwargs['element'])
        else:
            selector = 'Element not found'

        if strict:
            self.assertTrueWithScreenShot(self.exists(**kwargs), screenshot=screenshot,
                                          msg="Should see element with text or selector: '%s'" % selector)
        else:
            if not self.exists(**kwargs):
                errors = os.environ[SOFT_ASSERTIONS_FAILURES]

                self.event.assertion(data="*** FAILURE *** Element is missing: '%s'" % selector,
                                     screenshot=self.screenshot())

                errors += "\nElement is missing: '%s'" % selector
                os.environ[SOFT_ASSERTIONS_FAILURES] = errors
                os.environ[FAILURES_FOUND] = "true"
                self._page_source_to_console_log()
            else:
                self.event._log_info(self.event._event_data("*** SUCCESS *** Element is presented: '%s'" % selector))

    def verify_not_exists(self, strict=False, **kwargs):
        screenshot = False
        if kwargs.has_key('screenshot') and kwargs['screenshot']:
            screenshot = True

        if kwargs.has_key('name'):
            selector = kwargs['name']
        elif kwargs.has_key('accessibility_id'):
            selector = kwargs['accessibility_id']
        elif kwargs.has_key('class_name'):
            selector = kwargs['class_name']
        elif kwargs.has_key('id'):
            selector = kwargs['id']
        elif kwargs.has_key('xpath'):
            selector = kwargs['xpath']
        elif kwargs.has_key('element'):
            selector = str(kwargs['element'])
        else:
            selector = 'Element is absent'

        if strict:
            self.assertTrueWithScreenShot(not self.exists(**kwargs), screenshot=screenshot,
                                          msg="Should NOT see element with text or selector: '%s'" % selector)
        else:
            if self.exists(**kwargs):
                errors = os.environ[SOFT_ASSERTIONS_FAILURES]
                self.event.assertion(data="*** FAILURE *** Element is presented but should not be: '%s'" % selector,
                                     screenshot=self.screenshot())
                errors += "\nElement is presented but should not be: '%s'" % selector
                os.environ[SOFT_ASSERTIONS_FAILURES] = errors
                os.environ[FAILURES_FOUND] = "true"
                self._page_source_to_console_log()
            else:
                self.event._log_info(self.event._event_data("*** SUCCESS *** Element missing: '%s'" % selector))

    def verify_not_equal(self, obj1, obj2, screenshot=False):
        self.assertTrueWithScreenShot(obj1 != obj2, screenshot=screenshot,
                                      msg="'%s' should NOT equal '%s'" % (obj1, obj2))

    def verify_equal(self, obj1, obj2, screenshot=False):
        self.assertTrueWithScreenShot(obj1 == obj2, screenshot=screenshot, msg="'%s' should EQUAL '%s'" % (obj1, obj2))

    def _element_action(self, action, element=None, **kwargs):
        """Find element if not supplied and send to action delegate"""

        element = element if element else self._find_element(**kwargs)

        action(element)
        return element

    def _find_element(self, **kwargs):
        """
        Finds element by name or xpath
        """

        if kwargs.has_key('timeout'):
            self.set_implicit_wait(int(kwargs['timeout']))

        if kwargs.has_key('name'):
            return self._find_element_by_xpath(
                '//*[@text="{0}" or @content-desc="{1}"]'.format(kwargs['name'], kwargs['name']))
        elif kwargs.has_key('class_name'):
            return self._find_element_by_class_name(kwargs['class_name'])
        elif kwargs.has_key('id'):
            return self._find_element_by_id(kwargs['id'])
        elif kwargs.has_key('accessibility_id'):
            return self._find_element_by_accessibility_id(kwargs['accessibility_id'])
        elif kwargs.has_key('xpath'):
            return self._find_element_by_xpath(kwargs['xpath'])
        elif kwargs.has_key('element'):
            return kwargs['element']
        else:
            self.assertTrueWithScreenShot(False, msg="The element with provided args '{0}' was not found".format(str(kwargs)), screenshot=True)

    def _find_element_by_name(self, name):
        try:
            return self.driver.find_element_by_name(name)
        except:
            self.event.error(element_name=name)
            self.assertTrueWithScreenShot(False, msg="The element with NAME '{0}' cannot be found".format(name), screenshot=True)

    def _find_element_by_xpath(self, xpath):
        try:
            return self.driver.find_element_by_xpath(xpath)
        except:
            self.event.error(element_xpath=xpath)
            self.assertTrueWithScreenShot(False, msg="The element with XPATH '{0}' cannot be found".format(xpath), screenshot=True)

    def _find_element_by_class_name(self, class_name):
        try:
            return self.driver.find_element_by_class_name(class_name)
        except:
            self.event.error(element_name=class_name)
            self.assertTrueWithScreenShot(False, msg="The element with CLASS NAME '{0}' cannot be found".format(class_name), screenshot=True)

    def _find_element_by_id(self, element_id):
        try:
            return self.driver.find_element_by_id(element_id)
        except:
            self.event.error(id=element_id)
            self.assertTrueWithScreenShot(False, msg="The element with ID '{0}' cannot be found".format(element_id), screenshot=True)

    def _find_element_by_accessibility_id(self, element_accessibility_id):
        try:
            return self.driver.find_element_by_accessibility_id(element_accessibility_id)
        except:
            self.event.error(id=element_accessibility_id)
            self.assertTrueWithScreenShot(False, msg="The element with ACCESSIBILITY ID '{0}' cannot be found".format(element_accessibility_id), screenshot=True)

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
                sleep(1.0)
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

    def run_phantom_driver_click(self, selector):
        t1 = FuncThread(self.click_unappropriate_popup, selector)
        t1.start()
        t1.join()

    def click_unappropriate_popup(self, selector):
        # try:
        #     self.angel_driver.find_element_by_id(selector)
        # except:
        #     self.event.assertion("AirPlay popup", screenshot=self.screenshot())
        #     ta = TouchAction(self.angel_driver)
        #     ta.press(x=150, y=35).release().perform()

        pass

    def _page_source_to_console_log(self, data=None):

        #remove when ipad issue is fixed
        if 'iPad' in self.capabilities['deviceName']:
            pass
        else:
            try:
                page_source = data if data is not None else self.driver.page_source
                log = page_source.encode('utf-8')
                self.event._log_to_console_log(str(log))
            except:
                self.event._log_to_console_log('Error while logging page source')

class NoSuchAlertException(Exception):
    pass


class FuncThread(threading.Thread):
    def __init__(self, target, *args):
        self._target = target
        self._args = args
        threading.Thread.__init__(self)

    def run(self):
        self._target(*self._args)
