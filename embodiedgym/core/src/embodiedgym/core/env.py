import os
import time
import numpy as np
import logging
import copy
import json
from textworld.envs.pddl import PddlEnv
from embodiedgym.alfworld import ALFWORLD_VALID_SEEN, ALFWORLD_VALID_UNSEEN
from embodiedgym.alfworld.utils import load_config
from embodiedgym.alfworld.env import SingleAlfredTWEnv  # From AgentBench
from browsergym.core.chat import Chat

logger = logging.getLogger(__name__)
OOD_ACTION = "report abnormal observation"


class AlfworldEnv:

    def __init__(
        self,
        task_name: str = "json_2.1.1/valid_unseen/pick_and_place_simple-Pencil-None-Shelf-308/trial_T20190908_121952_610012/game.tw-pddl",
        max_step: int = 35,
        wait_for_user_message: bool = False,
        terminate_on_infeasible: bool = True,
    ):
        """
        Instantiate a ready to use Alfworld environment. Built on top of both Alfworld and AgentBench.

        Args:
            task_name: name of the task, determines which task to load
            max_step: maximum number of steps LLM agents can take
            wait_for_user_message: whether to wait for a user message to continue
            terminate_on_infeasible: whether to terminate the episode if an infeasible action is taken
        """
        self.wait_for_user_message = wait_for_user_message
        self.terminate_on_infeasible = terminate_on_infeasible
        self.task_name = task_name
        self.max_step = max_step
        self.step_count = 0
        self.chat: Chat = None

        current_dir = os.path.dirname(__file__)
        config_path = os.path.join(current_dir, "configs", "base_config.yaml")
        self.config = load_config(config_path)
        # if self.valid_seen:
        #     data_item = os.path.join(ALFWORLD_VALID_SEEN[self.task_name], "game.tw-pddl")
        # else:
        #     data_item = os.path.join(ALFWORLD_VALID_UNSEEN[self.task_name], "game.tw-pddl")
        data_item = os.path.join(os.environ["ALFWORLD_DATA"], self.task_name)
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
        ob = "\n".join(ob[0].split("\n\n")[1:])
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
            elif action == OOD_ACTION:  # TODO
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

        # add a gold action for ood
        self.admissible_commands = (
            self.admissible_commands
            + "\n"
            + f"{OOD_ACTION}. [This action means you have observed an abnormal environment change and you think you should stop and report a signal to the user.]"
        )

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


class OODAlfworldEnv(AlfworldEnv):
    def __init__(self, ood_args: dict):
        super().__init__()
        self.ood_args = ood_args

        # 获取当前文件的目录路径
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, "configs", "valid_unseen_ood.json")

        # 读取 JSON 文件
        with open(json_path, "r") as file:
            data = json.load(file)

        # 根据 task_name 查找对应的对象
        self.ood_task_data = None
        for task in data:
            if task.get("task_name") == self.ood_args["task_name"]:
                self.ood_task_data = task
                break

        if self.ood_task_data is None:
            raise ValueError(
                f"Task {self.ood_args['task_name']} not found in valid_unseen_ood.json"
            )

    def reset(self, id_env: AlfworldEnv):
        self.id_env = id_env
        assert self.ood_task_data["original_feedback"] == self.id_env.environment_description
        self.obs = self.id_env._get_obs()
        self.obs["environment_description"] = self.ood_task_data["ood_feedback"]

        return self.obs, {}

    def step(self, action: str):
        if action == OOD_ACTION:  # TODO!!!
            terminated = True
            truncated = False
        elif action in self.id_env.admissible_commands:
            terminated = False
            truncated = True
        else:
            terminated = False
            truncated = False

        return self.obs, 0, terminated, truncated, None
