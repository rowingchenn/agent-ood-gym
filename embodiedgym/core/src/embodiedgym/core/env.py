import os
import time
import numpy as np
import logging
import copy
from textworld.envs.pddl import PddlEnv
from embodiedgym.alfworld import ALFWORLD_VALID_SEEN, ALFWORLD_VALID_UNSEEN
from embodiedgym.alfworld.utils import load_config
from embodiedgym.alfworld.env import SingleAlfredTWEnv  # From AgentBench
from browsergym.core.chat import Chat

logger = logging.getLogger(__name__)


class AlfworldEnv:
    def __init__(
        self,
        config_path: str,
        valid_seen: bool = False,
        task_index: int = 0,
        max_step: int = 35,
        wait_for_user_message: bool = False,
        terminate_on_infeasible: bool = True,
    ):
        """
        Instantiate a ready to use Alfworld environment. Built on top of both Alfworld and AgentBench.

        Args:
            config_path: path to the config file, LLMAgentOODGym/agent_ood_gym/embodiedgym/alfworld/configs/base_config.yaml
            valid_seen: whether to use the valid seen dataset
            task_index: index of the task in the dataset, determines which task to load
            wait_for_user_message: whether to wait for a user message to continue
            terminate_on_infeasible: whether to terminate the episode if an infeasible action is taken
        """
        self.wait_for_user_message = wait_for_user_message
        self.terminate_on_infeasible = terminate_on_infeasible
        self.valid_seen = valid_seen
        self.task_index = task_index
        self.max_step = max_step
        self.step_count = 0
        self.chat: Chat = None
        self.config = load_config(config_path)
        if self.valid_seen:
            data_item = os.path.join(ALFWORLD_VALID_SEEN[self.task_index], "game.tw-pddl")
        else:
            data_item = os.path.join(ALFWORLD_VALID_UNSEEN[self.task_index], "game.tw-pddl")
        self.env = SingleAlfredTWEnv(self.config, data_item)
        self.env = self.env.init_env(batch_size=1)

    def reset(self):
        # create a new chat, this is not only for recording actions from the agent
        # but also could be shown on the screen as a chatbox using the Chromium browser
        self.chat = Chat(
            headless=False,
            chat_size=(500, 800),
            record_video_dir=None,
        )

        # obs: Text observations, i.e. command's feedback.
        # infos: Information requested when creating the environments.
        self.ob, self.task_info = self.env.reset()

        self.ob = self.ob.split("Your task is to: ")
        self.goal_object = self.ob[1]
        self.environment_description = self.ob[0]
        self.admissible_commands = "\n".join(self.task_info.get("admissible_commands", [[]])[0])

        if self.goal_object is None:
            self.goal_object = []
        elif isinstance(self.goal_object, str):
            self.goal_object = [{"type": "text", "text": self.goal_object}]
        elif isinstance(self.goal_object, list):
            self.goal_object = self.goal_object
        else:
            raise ValueError(
                f"task_goal should be of type str or list, got {self.goal_object.__class__}"
            )

        self.chat.add_message(
            role="assistant",
            msg="Hi! I am your househould assistant, I can perform household tasks for you. What can I help you with?",
        )

        # send task goal (if any) to the chat
        for message in self.goal_object:
            match message["type"]:
                case "text":
                    self.chat.add_message(role="user", msg=message["text"])
                case "image_url":
                    image_src = message["image_url"]
                    if isinstance(image_src, dict):
                        image_src = image_src["url"]
                    self.chat.add_message(role="user_image", msg=image_src)
                case _:
                    raise ValueError(
                        f"Unknown message type {repr(message['type'])} in the task goal."
                    )

        # init start time
        self.start_time = time.time()

        # no action yet
        self.last_action = ""
        self.last_action_error = ""
        self.infeasible_message_received = False

        # wait for a user message to continue if it's configured to wait for a user message
        self._wait_for_user_message()

        self.obs = self._get_obs()

        info = {}
        info["task_info"] = self.task_info
        return self.obs, info

    def step(self, action: str):
        self.last_action = action
        self.step_count += 1
        info = {}
        info["action_exec_start"] = time.time()
        info["action_exec_timeout"] = 0

        logger.debug(f"Executing action: {action}")

        if action not in self.admissible_commands:
            if action == "infeasible":  # TODO
                self.infeasible_message_received = True
            elif action == "report OOD":  # TODO
                pass
            else:
                self.last_action_error = (
                    f"Action {action} is not valid. It's not in the admissible commands!"
                )
                obs = self._get_obs()
                terminated = False
                truncated = self.step_count >= self.max_step
                return obs, 0, terminated, truncated, None  # is it right to return None as info?
        # action is promised to be in the admissible commands
        # it's designed in agents _parse_answer() function
        observation, reward, done, task_info = self.env.step(action)
        self.environment_description, reward, done = (
            observation[0],
            task_info["won"][0],
            done[0],
        )
        self.admissible_commands = "\n".join(task_info.get("admissible_commands", [[]])[0])

        logger.debug(f"Action executed")
        info["action_exec_stop"] = time.time()

        self._wait_for_user_message()
        logger.debug(f"User message done")

        info["task_info"] = task_info
        obs = self._get_obs()
        # terminate the episode if the agent is infeasible or the episode is done
        terminated = done or (
            self.terminate_on_infeasible and self.infeasible_message_received
        )  # task or agent can terminate the episode
        truncated = self.step_count >= self.max_step
        return obs, reward, terminated, truncated, info

    def _get_obs(self):
        obs = {
            "chat_messages": tuple(copy.deepcopy(self.chat.messages)),
            "goal_object": tuple(copy.deepcopy(self.goal_object)),
            "environment_description": self.environment_description,
            "admissible_commands": self.admissible_commands,
            "last_action": self.last_action,
            "last_action_error": self.last_action_error,
            "elapsed_time": np.asarray([time.time() - self.start_time]),
        }
        return obs

    def _wait_for_user_message(self):
        # if last message is from the assistant, wait for a user message to continue
        # TODO: be smarter about when to wait for a user message (different action from the assistant?)
        if self.chat.messages[-1]["role"] == "assistant" and self.wait_for_user_message:
            self.chat.wait_for_user_message()
