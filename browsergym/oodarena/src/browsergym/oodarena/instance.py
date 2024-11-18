import logging
import os
import time

import playwright.sync_api
import requests

logger = logging.getLogger(__name__)

class OODArenaInstance:
    """
    Utility class to access a OODArena instance.

    """

    def __init__(
        self,
    ) -> None:

        
        # TODO
        self.urls = {
            "advertisement":""
        }

        # self.home_url = HOMEPAGE

        # self.credentials = ACCOUNTS

    def full_reset(self):
        base_url = os.environ.get(self.RESET_URL_VAR, None)
        reset_url = f"{base_url}/reset"
        status_url = f"{base_url}/status"

        assert (
            reset_url
        ), f"Environment variable {self.RESET_URL_VAR} is missing or empty, required for a full instance reset."

        logger.info(f"Initiating {self.__class__.__name__} instance reset.")

        # trigger instance reset
        response = requests.get(reset_url)
        match response.status_code:
            case 200:
                logger.info(f"Reset started.")
            case 418:
                logger.warning("Reset was already running.")
            case _:
                raise Exception(
                    f"{self.__class__.__name__} reset request {reset_url} failed ({response.status_code}): {response.text}"
                )

        # wait until reset complete
        retry_after = 20  # 20 seconds wait between status checks
        timeout = 10 * 60  # 10 minutes timeout
        start_time = time.time()
        while True:
            # request instance status
            response = requests.get(status_url)
            # check for server error
            if response.status_code != 200:
                raise Exception(
                    f"{self.__class__.__name__} status request {status_url} failed ({response.status_code}): {response.text}"
                )
            # check for readiness
            if response.text == "Ready for duty!":
                break
            # check for timeout
            time_elapsed = time.time() - start_time
            logger.info(f"Reset still running after {time_elapsed:.0f} seconds...")
            if time_elapsed > timeout:
                raise Exception(
                    f"Reset still running after {time_elapsed} seconds (> {timeout}), aborting."
                )
            # wait a bit before next retry
            time.sleep(retry_after)

        # warm-start the instance (navigate to every domain)
        retries_left = 3
        while retries_left:
            retries_left -= 1
            try:
                self._check_is_reachable(
                    timeout=60
                )  # 60 seconds, warming up after reset might be slow
                break
            except Exception as e:
                if not retries_left:
                    raise
                logger.info(
                    f"Instance unresponsive after reset, retrying ({retries_left} retries left)\n{e}"
                )

    def check_status(self):
        """
        Check the status of the instance. Raises an error if the instance is not ready to be used.

        """
        self._check_is_reachable(timeout=10)  # 10 seconds

    def _check_is_reachable(self, timeout: int):
        """
        Test that every website is reachable.

        """
        for site, url in self.urls.items():
            try:
                requests.get(url, timeout=timeout)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                raise RuntimeError(
                    f'WebArena site "{site}" ({url}) is not reacheable. Please check the URL.'
                )

    def ui_login(self, site: str, page: playwright.sync_api.Page):
        """
        Should only be called once per site (expects user to be logged out).
        """

        url = self.urls[site]

        # open a new page (tab) to perform the login
        page = page.context.new_page()

        match site:
            case "reddit":
                username = self.credentials[site]["username"]
                password = self.credentials[site]["password"]

                page.goto(f"{url}")
                page.get_by_role("link", name="Log in").click()
                page.get_by_label("Username").fill(username)
                page.get_by_label("Password").fill(password)
                page.get_by_role("button", name="Log in").click()

            case "gitlab":
                username = self.credentials[site]["username"]
                password = self.credentials[site]["password"]

                page.goto(f"{url}/users/sign_in")
                page.get_by_label("Username or email").fill(username)
                page.get_by_label("Password").fill(password)
                page.get_by_role("button", name="Sign in").click()

            case "shopping":
                username = self.credentials[site]["username"]
                password = self.credentials[site]["password"]

                page.goto(f"{url}/customer/account/login/")
                page.get_by_label("Email", exact=True).fill(username)
                page.get_by_label("Password", exact=True).fill(password)
                page.get_by_role("button", name="Sign In").click()

            case "shopping_admin":
                username = self.credentials[site]["username"]
                password = self.credentials[site]["password"]

                page.goto(url)
                page.get_by_label("Username").fill(username)
                page.get_by_label("Password").fill(password)
                page.get_by_role("button", name="Sign in").click()

            case "wikipedia":
                page.goto(url)

            case "map":
                page.goto(url)

            case _:
                raise ValueError

        # release login page
        page.close()