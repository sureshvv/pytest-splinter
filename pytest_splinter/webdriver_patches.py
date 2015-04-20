"""Selenium webdriver monkey patches.

Patches are temporary fixes for issues raised in we selenium google project:
http://code.google.com/p/selenium/issues/detail?id=5175
http://code.google.com/p/selenium/issues/detail?id=5176.
"""

import time  # pragma: no cover
import os  # pragma: no cover
import socket  # pragma: no cover

from selenium.webdriver.remote import webelement, remote_connection  # pragma: no cover
from selenium.webdriver.firefox import webdriver  # pragma: no cover
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver  # pragma: no cover
from selenium.webdriver.android.webdriver import WebDriver as AndroidDriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.command import Command


class LocalFileDetector(object):  # pragma: no cover

    """Overriden LocalFileDetector to inject correct file_path check."""

    @classmethod
    def is_local_file(cls, *keys):
        """Correctly handle file inputs."""
        file_path = ''
        typing = []
        for key in keys:
            if isinstance(key, webelement.Keys):
                typing.append(key)
            elif isinstance(key, int):
                key = str(key)
                for i in range(len(key)):
                    typing.append(key[i])
            else:
                for i in range(len(key)):
                    typing.append(key[i])
        file_path = ''.join(typing)

        if file_path is '':
            return None

        try:
            # we added os.path.isabs(file_path) to ensure it's path and not just string
            if os.path.isabs(file_path) and os.path.exists(file_path):
                return file_path
        except:
            pass
        return None


# Get the original _request and store for future use in the monkey patched version as 'super'
old_request = remote_connection.RemoteConnection._request  # pragma: no cover
# save the original execute
RemoteWebDriver._base_execute = RemoteWebDriver.execute  # pragma: no cover
# save the original send_keys
old_send_keys = webelement.WebElement.send_keys

def send_keys_patch(self, *value):
    """ phantomjs 1.9.7/8 and 2.0 hang on send_keys for an input element of type file send_keys """
    from selenium.webdriver.phantomjs.webdriver import WebDriver as PhantomJsWebdriver
    if self.get_attribute('type') == 'file' and type(self.parent) == PhantomJsWebdriver:
        local_file = self.parent.file_detector.is_local_file(*value)
        if local_file is None:
            return
        try:
            return self._execute(Command.UPLOAD_FILE,
                        {'filepath': [local_file],
                         'selector': 'input[type=file]'})['value']
        except WebDriverException as e:
            if "Unrecognized command: POST" in e.__str__():
                return filename
            elif "Command not found: POST " in e.__str__():
                return filename
            elif '{"status":405,"value":["GET","HEAD","DELETE"]}' in e.__str__():
                return filename
            else:
                raise e
    return old_send_keys(self, *value)

def patch_webdriver(selenium_timeout):
    """Patch selenium webdriver to add functionality/fix issues."""
    def _request(*args, **kwargs):
        """Override _request to set socket timeout to some appropriate value."""
        timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(selenium_timeout)
            return old_request(*args, **kwargs)
        finally:
            socket.setdefaulttimeout(timeout)

    # Apply the monkey patche for RemoteConnection
    remote_connection.RemoteConnection._request = _request
    # Apply the monkey patch for LocalFileDetector
    webelement.LocalFileDetector = LocalFileDetector
    webelement.WebElement.send_keys = send_keys_patch

    # Apply the monkey patch to Firefox webdriver to disable native events
    # to avoid click on wrong elements, totally unpredictable
    # more info http://code.google.com/p/selenium/issues/detail?id=633
    webdriver.WebDriver.NATIVE_EVENTS_ALLOWED = False

    def execute(self, driver_command, params=None):
        if driver_command == 'setWindowSize':
            if type(self) == AndroidDriver:
                result = {u'status': 0, u'name': u'setWindowSize', u'value': u''}
                return result
        result = self._base_execute(driver_command, params)
        speed = self.get_speed()
        if speed > 0:
            time.sleep(speed)  # pragma: no cover
        return result

    def get_current_window_info(self):
        atts = self.execute_script("return [ window.id, window.name, document.title, document.url ];")
        atts = [
            att if att is not None and len(att) else 'undefined'
            for att in atts]
        return (self.current_window_handle, atts[0], atts[1], atts[2], atts[3])

    def current_window_is_main(self):
        return self.current_window_handle == self.window_handles[0]

    def set_speed(self, seconds):
        self._speed = seconds

    def get_speed(self):
        if not hasattr(self, '_speed'):
            self._speed = float(0)
        return self._speed

    RemoteWebDriver.set_speed = set_speed
    RemoteWebDriver.get_speed = get_speed
    RemoteWebDriver.execute = execute
    RemoteWebDriver.get_current_window_info = get_current_window_info
    RemoteWebDriver.current_window_is_main = current_window_is_main
