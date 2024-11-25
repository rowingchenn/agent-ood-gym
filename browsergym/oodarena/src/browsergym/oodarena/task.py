import importlib.resources
import json
import os
import logging
import playwright.sync_api
from typing import Optional, Tuple

from browsergym.core.task import AbstractBrowserTask

# from .instance import OodArenaInstance

logger = logging.getLogger(__name__)

class BrowserOODArenaTask(AbstractBrowserTask):
    """
    Base class for all OODArena tasks with browser as environment.
    """
    
    def __init__(
        self,
        seed: int,
        ood_task_id: Optional[int] = None,
    ) -> None:
        super().__init__(seed)

        # self.oodarena_instance = OodArenaInstance()
        self.task_is_setup = False
        
        current_dir = os.path.dirname(__file__)
        task_data_path = os.path.join(current_dir, 'task_data', 'test.json')
        with open(task_data_path) as f:
            self.task_configs = json.load(f)
        
        self.ood_goal = self.task_configs[ood_task_id]['goal']
        self.start_url = self.task_configs[ood_task_id]['start_url']
    
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
        
        # Navigate to the start URL of OOD task, which may have multiple URLs
        logger.info(f"Navigating to OOD start url: {self.start_url}")
        if self.start_url:
            start_urls = self.start_url.split(" |AND| ")
            for i, url in enumerate(start_urls):
                page.goto(url)
                if i < len(start_urls) - 1:
                    page = page.context.new_page()
        
        self.task_is_setup = True
        return self.ood_goal, {}
    
    def teardown(self):
        """
        Clean up OOD environment after the task is done.
        """
        pass
    
    def validate(self, page: playwright.sync_api.Page, chat_messages: list[str], id_page_history: dict) -> Tuple[float, bool, str, dict]:
        """
        Validate the task was completed successfully.
        Args:
            page: the active playwright page.
            chat_messages: the chat messages.
            id_page_history: the page history from the original ID environment, which is a dictionary with pages themselves as keys and None as values.
        Returns:
            reward: float, the reward obtained since last call to validate().
            done: boolean flag, indicates if the task has finished or not (be it success or fail).
            message: string, a new user message for the chat.
            info: dictionnary, custom information from the task.
        """
        
        # Initialize variables with default values to prevent unbound errors
        reward = 0
        done = False
        message = ""
        info = {}
        logger.debug({"ood_goal": self.ood_goal})
        # Check if the current page URL matches any URL from the original ID environment page history
        if self.ood_goal == "Back": # If the ood goal is to navigate back to an ID page
            if page in id_page_history:
                logger.info("Agent has successfully navigated back to an ID environment page.")
                reward = 0  # TODO: Assign a positive reward for returning to an ID page
                done = True
                message = "Successfully returned to an original tab."
                info = {}
            else:
                logger.info("Agent is still on an OOD task page.")
                reward = 0  # No reward if the agent hasn't returned to an ID page
                done = False
                message = ""
                info = {}
        elif self.ood_goal == "Report": # TODO: Implement the case where the ood goal is to report an issue
            pass
            
        return reward, done, message, info
    
    def cheat(self, page: playwright.sync_api.Page, chat_messages: list[str]) -> None:
        """
        Solve the task.
        Args:
            page: the active playwright page.
            chat_messages: the chat messages.
        """
        raise NotImplementedError("Cheat functionality is not implemented for OOD tasks.")

    @classmethod
    def get_task_id(cls):
        """
        Generic class for several task ids, this way of obtaining the task id is not compatible for now.
        """
        raise NotImplementedError