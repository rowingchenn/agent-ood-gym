import importlib.resources
import json
import os
import logging
import playwright.sync_api
from typing import Optional, Tuple

from browsergym.core.task import AbstractBrowserTask

from .instance import OodArenaInstance

logger = logging.getLogger(__name__)

class BrowserOODArenaTask(AbstractBrowserTask):
    """
    Base class for all OODArena tasks with browser as environment.
    """
    
    def __init__(
        self,
        seed: int,
        task_id: Optional[int] = None,
        intent_template_id: Optional[int] = None,
        with_na_hint: bool = False,
        with_homepage_hint: bool = False,
    ) -> None:
        super().__init__(seed)

        # task properties, will be used to set up the browsergym environment
        self.viewport = {"width": 1280, "height": 720}
        self.slow_mo = 1000
        self.timeout = 30000
        self.oodarena_instance = OodArenaInstance()
        self.task_is_setup = False
        
        current_dir = os.path.dirname(__file__)
        task_data_path = os.path.join(current_dir, 'task_data', 'test.json')
        with open(task_data_path) as f:
            self.task_configs = json.load(f)
        
        # TODO: should goal be the original ID goal? so may need to be passed as argument?
        self.goal = self.task_configs[task_id]['goal']
    
    def setup(self, page: playwright.sync_api.Page) -> Tuple[str, dict]:
        """
        Set up everything needed to execute the task.
        Args:
            page: the active playwright page.
        Returns:
            goal: str, goal of the task.
            info: dict, custom information from the task.
        """
        logging.debug("Setting up the OOD task")
        if self.task_is_setup:
            return ValueError("The task is already setup")
        
        self.page = page
        # Set the page timeout
        page.set_default_timeout(self.timeout)
        
        logger.info(f"Navigating to OOD start url: {self.start_url}")
        page.goto(self.start_url)
        
        self.task_is_setup = True
        return self.goal, {}
    
    def teardown(self):
        """
        Clean up OOD environment after the task is done.
        """
        pass
    
    def validate(self, page: playwright.sync_api.Page, chat_messages: list[str]) -> Tuple[float, bool, str, dict]:
        """
        Validate the task was completed successfully
        Args:
            page: the active playwright page.
            chat_messages: the chat messages.
        Returns:
            reward: float, the reward obtained since last call to validate().
            done: boolean flag, indicates if the task has finished or not (be it success or fail).
            message: string, a new user message for the chat.
            info: dictionnary, custom information from the task.
        """
        pass
    
    def cheat(self, page: playwright.sync_api.Page, chat_messages: list[str]) -> None:
        """
        Solve the task.
        Args:
            page: the active playwright page.
            chat_messages: the chat messages.
        """
        pass
        
