import copy
import gzip
import importlib.metadata
import json
import logging
import os
import pickle
import re
import sys
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

import gymnasium as gym
import numpy as np
from dataclasses_json import DataClassJsonMixin
from PIL import Image
from tqdm import tqdm

from browsergym.core.chat import Chat
from browsergym.core.action.parsers import highlevel_action_parser

from browsergym.experiments.agent import Agent
from browsergym.experiments.utils import count_messages_token, count_tokens
from browsergym.experiments.loop import AbstractAgentArgs, save_package_versions

from embodiedgym.alfworld.utils import load_config, load_prompts
from embodiedgym.alfworld import ALFWORLD_VALID_SEEN, ALFWORLD_VALID_UNSEEN
from embodiedgym.core.env import AlfworldEnv, OODAlfworldEnv
from embodiedgym.core.env import OOD_ACTION

logger = logging.getLogger(__name__)

SEED_MAX = 2 ^ 32  # arbitrary max value (exclusive), seems large enough


@dataclass
class AlfworldEnvArgs(DataClassJsonMixin):
    # config_path: str  # embodiedgym/alfworld/configs/base_config.yaml
    # prompts_path: str  # embodiedgym/alfworld/prompts/alfworld_multiturn_plan_first.json
    # valid_seen: bool = False
    task_name: int = 0
    max_step: int = 35
    wait_for_user_message: bool = False
    terminate_on_infeasible: bool = True

    def make_env(
        self,
        ood_args: dict = None,
    ):
        if ood_args is not None:
            assert ood_args["task_name"] == self.task_name
            env = OODAlfworldEnv(
                ood_args=ood_args,
            )
        else:
            env = AlfworldEnv(
                task_name=self.task_name,
                max_step=self.max_step,
                wait_for_user_message=self.wait_for_user_message,
                terminate_on_infeasible=self.terminate_on_infeasible,
            )
        return env


@dataclass
class ExpArgs:
    """Arguments to run an experiment, i.e. run agent in an environment until done.

    This dataclass is used to store experiments arguments. It contains
    agent_args and env_args which follows the same principle. It contains helper
    functions to prepare and run experiments.

    Attributes:
    -----------
    agent_args: AbstractAgentArgs
        The arguments to instantiate the agent.
    env_args: EnvArgs
        The arguments to instantiate the environment.
    exp_dir: str
        The directory where the experiment will be saved.
    exp_name: str
        The name of the experiment. If None, it will be generated from the
        agent and environment names.
    enable_debug: bool
        If python is running in debug mode and `enable_debug` is True, errors
        will be raised instead of only logged
    error_msg: str
        Error that occured while running the experiment (if any).
    stack_trace: str
        Stack trace of the error (if any).
    order: int (internal)
        The order of the experiment in the batch. It is used to keep track of
        the original order of the experiments in case they are shuffled.
    ood_args: dict
        ood_task_id: int, the ID of the OOD task. Unique for each OOD task.
        ood_insert_step: int, the step at which the OOD task should be inserted. must be within the range of the episode.
        ood_max_steps: int, the maximum number of steps we allow agent to expore OOD environments.
    """

    agent_args: AbstractAgentArgs
    env_args: AlfworldEnvArgs
    exp_dir: str = None
    exp_name: str = None
    enable_debug: bool = True
    err_msg: str = None
    stack_trace: str = None
    order: int = None  # use to keep the original order the experiments were meant to be launched.
    logging_level: int = logging.INFO
    logging_level_stdout: int = logging.INFO
    exp_id: str = None
    ood_args: Dict[str, any] = None

    def make_id(self):
        """Create a unique id for the experiment."""
        if self.exp_id is None:
            self.exp_id = str(uuid.uuid4())

    def prepare(self, exp_root):
        """Prepare the experiment directory and save the experiment arguments.

        This enables inspecting experiments that are not run yet.
        """

        if self.exp_name is None:
            task_name = self.env_args.task_name
            if self.ood_args is not None:
                self.exp_name = f"embodiedgym_{self.agent_args.agent_name}_on_{task_name}_oodarena.{self.ood_args['task_id']}"
            else:
                self.exp_name = f"embodiedgym_{self.agent_args.agent_name}_on_{task_name}"

        # if exp_dir exists, it means it's a re-run, move the old one
        if self.exp_dir is not None:
            _move_old_exp(self.exp_dir)

        self.make_id()

        self.exp_date = datetime.now()
        self._make_dir(exp_root)

        self.exp_dir.mkdir(parents=True, exist_ok=True)
        with open(self.exp_dir / "exp_args.pkl", "wb") as f:
            pickle.dump(self, f)

    def _make_dir(self, exp_root):
        """Create a unique directory for the experiment."""
        date_str = self.exp_date.strftime("%Y-%m-%d_%H-%M-%S")
        exp_str = re.sub(
            r"[\/:*?<>|]", "_", self.exp_name
        )  # sanitize exp_name to be used as a file name (substitute forbidden characters)

        for i in range(1000):
            if i >= 999:  # make sure we don't loop forever
                raise ValueError("Could not find a unique name for the experiment directory.")

            tag = f"_{i}" if i > 0 else ""
            self.exp_dir = Path(exp_root) / f"{date_str}_{exp_str}{tag}"
            if not self.exp_dir.exists():
                break

    # TODO distinguish between agent error and environment or system error. e.g.
    # the parsing error of an action should not be re-run.
    def run(self):
        """Run the experiment and save the results"""

        # start writing logs to run logfile
        self._set_logger()

        # log python environment info
        save_package_versions(self.exp_dir)

        episode_info = []
        env, step_info, err_msg, stack_trace = None, None, None, None
        ood_env, ood_step_info = None, None
        try:
            logger.info(f"Running experiment {self.exp_name} in:\n  {self.exp_dir}")
            agent = self.agent_args.make_agent()
            logger.debug(f"Agent created.")

            env = self.env_args.make_env()

            logger.debug(f"Environment created.")

            step_info = StepInfo(step=0)
            episode_info = [step_info]
            step_info.from_reset(
                env, obs_preprocessor=agent.obs_preprocessor
            )  # TODO: obs_preprocessor need to be redesigned in agents
            logger.debug(f"Environment reset, first observation received and first step created.")

            if self.ood_args != None:
                self.ood_done = False  # 用来跳出ood的episode
            else:
                self.ood_done = True

            while not step_info.is_done:  # when truncated or terminated, the episode is done
                if (
                    not self.ood_done
                    and self.ood_args["original_feedback"].strip()
                    == step_info.obs["environment_description"].strip()
                ):  # simulate OOD observation step
                    ood_env = self.env_args.make_env(
                        ood_args=self.ood_args,
                    )
                    logger.debug(f"OOD Environment created.")

                    # TODO
                    ood_step_info = StepInfo(step=-1)  # use -1 to indicate OOD step
                    ood_step_info.from_reset_ood(
                        ood_env=ood_env,
                        id_env=env,
                        obs_preprocessor=agent.obs_preprocessor,
                    )
                    logger.debug(
                        "OOD environment reset, OOD observation received and OOD step created."
                    )
                    while not ood_step_info.is_done:
                        logger.debug(f"Starting OOD step {ood_step_info.step}.")
                        ood_action = ood_step_info.from_action(agent)
                        logger.debug(f"Agent chose action on OOD observation:\n {ood_action}")

                        # if agent failed to parse the action, we should end the OOD episode and continue with the ID episode
                        # and we mark the OOD episode as truncated
                        if ood_action is None:
                            ood_step_info.truncated = True

                        ood_step_info.save_step_info(
                            self.exp_dir,
                        )
                        logger.debug(f"OOD step info saved.")

                        # _send_chat_info(
                        #     ood_env.unwrapped.chat, ood_action, ood_step_info.agent_info
                        # )
                        # logger.debug(f"Chat info sent.")

                        if ood_action is None:
                            logger.debug(
                                f"Agent returned None action in OOD environments. Ending OOD episode."
                            )
                            break

                        # we use negative step number to indicate OOD steps
                        ood_step_info = StepInfo(step=ood_step_info.step - 1)
                        episode_info.append(ood_step_info)

                        ood_step_info.from_step(
                            env=ood_env, action=ood_action, obs_preprocessor=agent.obs_preprocessor
                        )
                    self.ood_done = True
                else:  # normal step
                    logger.info(f"Starting step {step_info.step}.")
                    action = step_info.from_action(agent)
                    logger.info(f"Agent chose action:\n {action}")

                    if action is None:
                        # will end the episode after saving the step info.
                        step_info.truncated = True

                    step_info.save_step_info(self.exp_dir)
                    logger.debug(f"Step info saved.")

                    # _send_chat_info(env.unwrapped.chat, action, step_info.agent_info)
                    # logger.debug(f"Chat info sent.")

                    if action is None:
                        logger.debug(f"Agent returned None action. Ending episode.")
                        break

                    step_info = StepInfo(step=step_info.step + 1)
                    episode_info.append(step_info)

                    logger.debug(f"Sending action to environment.")
                    step_info.from_step(env, action, obs_preprocessor=agent.obs_preprocessor)
                    logger.debug(f"Environment stepped.")
                    logger.info(
                        f"Environment description: {step_info.obs['environment_description']}"
                    )

        except Exception as e:
            err_msg = f"Exception uncaught by agent or environment in task {self.env_args.task_name}.\n{type(e).__name__}:\n{e}"
            stack_trace = traceback.format_exc()

            self.err_msg = err_msg
            self.stack_trace = stack_trace

            logger.warning(err_msg + "\n" + stack_trace)
            if _is_debugging() and self.enable_debug:
                logger.warning("Debug mode is enabled. Raising the error.")
                raise

        finally:
            try:
                if step_info is not None:
                    step_info.save_step_info(self.exp_dir)
            except Exception as e:
                logger.error(f"Error while saving step info in the finally block: {e}")
            try:
                if (
                    not err_msg
                    and len(episode_info) > 0
                    and not (episode_info[-1].terminated or episode_info[-1].truncated)
                ):
                    e = KeyboardInterrupt("Early termination??")
                    err_msg = f"Exception uncaught by agent or environment in task {self.env_args.task_name}.\n{type(e).__name__}:\n{e}"
                logger.info(f"Saving summary info.")
                _save_summary_info(episode_info, self.exp_dir, err_msg, stack_trace)
            except Exception as e:
                logger.error(f"Error while saving summary info in the finally block: {e}")
            try:
                if env is not None:
                    env.close()
            except Exception as e:
                logger.error(f"Error while closing the environment in the finally block: {e}")
            try:
                self._unset_logger()  # stop writing logs to run logfile
            except Exception as e:
                logger.error(f"Error while unsetting the logger in the finally block: {e}")

    def _set_logger(self):
        # output logging traces to a log file
        file_handler = logging.FileHandler(self.exp_dir / "experiment.log")
        file_handler.setLevel(self.logging_level)  # same level as console outputs
        formatter = logging.Formatter(
            "%(asctime)s - %(process)d - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        # output handler
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(self.logging_level_stdout)
        stream_handler.setFormatter(formatter)
        # setup root logger
        root_logger = logging.getLogger()

        # remove previous stream handlers
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                root_logger.removeHandler(handler)

        root_logger.setLevel(self.logging_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(stream_handler)
        # setup openai logger (don't go below INFO verbosity)
        openai_logger = logging.getLogger("openai._base_client")
        openai_logger.setLevel(max(logging.INFO, self.logging_level))

        self.logging_file_handler = file_handler

    def _unset_logger(self):
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.logging_file_handler)


@dataclass
class StepTimestamps:
    env_start: float = 0
    action_exec_start: float = 0  # to extract begining of visual action from video
    action_exec_stop: float = 0  # to extract end of visual action from video
    action_exect_after_timeout: float = 0
    env_stop: float = 0
    agent_start: float = 0
    agent_stop: float = 0


@dataclass
class StepInfo:
    """Collects information about step that will be saved and reloaded.
    Helper functions only modify the dataclass attributes and helps keeping the
    information organized.

    Attributes:
    -----------
    step: int
        The step number of the episode.
    obs: dict
        The observation of the environment.
    reward: float
        The reward of the step.
    raw_reward: float
        The raw reward of the step.
    terminated: bool
        Whether the episode is terminated i.e. reached a terminal state. report OOD signal. report infeasible message.
    truncated: bool
        Whether the episode is truncated i.e. reached a maximum number of steps.
    ood_detected: bool
        Whether the OOD detection is triggered. True means the LLM agent reports an OOD signal and the episode is terminated.
    action: str
        The action taken by the agent.
    agent_info: dict
        Additional information from the agent.
    stats: dict
        Extra statistics about the step.
    profiling: StepTimestamps
        Timestamps of the different events during the episode.
    """

    step: int = None
    obs: dict = None
    reward: float = 0
    raw_reward: float = 0
    terminated: bool = None
    truncated: bool = None
    ood_detected: bool = None
    action: str = None
    agent_info: dict = field(default_factory=dict)
    stats: dict = None
    profiling: StepTimestamps = field(default_factory=StepTimestamps)
    task_info: dict = None

    def from_step(self, env: gym.Env, action: str, obs_preprocessor: callable):
        t = self.profiling
        t.env_start = time.time()
        self.obs, self.reward, self.terminated, self.truncated, env_info, self.ood_detected = (
            env.step(action)
        )
        t.env_stop = time.time()

        self.task_info = env_info.get("task_info", None)

        self.raw_reward = env_info.get("RAW_REWARD_GLOBAL", None)

        t.action_exec_start = env_info["action_exec_start"]  # start
        t.action_exect_after_timeout = env_info["action_exec_stop"]
        t.action_exec_stop = env_info["action_exec_stop"] - env_info["action_exec_timeout"]

        # if obs_preprocessor:
        #     self.obs = obs_preprocessor(self.obs)

    def from_action(self, agent: Agent):
        self.profiling.agent_start = time.time()
        self.action, self.agent_info = agent.get_action(self.obs.copy())
        self.profiling.agent_stop = time.time()

        self.make_stats()

        return self.action

    def from_reset(self, env: gym.Env, obs_preprocessor: callable):
        t = self.profiling
        t.env_start = time.time()
        self.obs, env_info = env.reset()
        t.env_stop = time.time()

        t.action_exec_start = env_info.get("recording_start_time", t.env_start)
        t.action_exect_after_timeout = t.env_stop
        t.action_exec_stop = t.env_stop

        # 这里有个莫名其妙的Bug，就是如果obs_preprocessor里面是pass，那么self.obs就会变成None
        # if obs_preprocessor:
        #     self.obs = obs_preprocessor(self.obs)

    def from_reset_ood(
        self, ood_env: OODAlfworldEnv, id_env: AlfworldEnv, obs_preprocessor: callable
    ):
        t = self.profiling
        t.env_start = time.time()
        # TODO: reset a embodied ood env should use different logic
        self.obs, env_info = ood_env.reset(id_env=id_env)
        t.env_stop = time.time()

        t.action_exec_start = env_info.get("recording_start_time", t.env_start)
        t.action_exect_after_timeout = t.env_stop
        t.action_exec_stop = t.env_stop

        # if obs_preprocessor:
        #     self.obs = obs_preprocessor(self.obs)

    @property
    def is_done(self):
        return self.terminated or self.truncated

    def make_stats(self):

        stats = {
            f"n_token_{key}": count_tokens(val)
            for key, val in self.obs.items()
            if isinstance(val, str)
        }
        stats.update(self.agent_info.pop("stats", {}))

        messages = self.agent_info.get("chat_messages", None)
        if messages is not None:
            stats["n_token_agent_messages"] = count_messages_token(messages)

        t = self.profiling
        stats["step_elapsed"] = t.env_stop - t.env_start
        stats["agent_elapsed"] = t.agent_stop - t.agent_start

        self.stats = stats

    def save_step_info(self, exp_dir, save_json=False):

        # special treatment for some of the observation fields
        if self.obs is not None:
            # save goal object (which might contain images) to a separate file to save space
            if self.obs.get("goal_object", False):
                # save the goal object only once (goal should never change once setup)
                goal_object_file = Path(exp_dir) / "goal_object.pkl.gz"
                if not goal_object_file.exists():
                    with gzip.open(goal_object_file, "wb") as f:
                        pickle.dump(self.obs["goal_object"], f)
                # set goal_object to a special placeholder value, which indicates it should be loaded from a separate file
                self.obs["goal_object"] = None

        with gzip.open(exp_dir / f"step_{self.step}.pkl.gz", "wb") as f:
            pickle.dump(self, f)

        if save_json:
            with open(exp_dir / "steps_info.json", "w") as f:
                json.dump(self, f, indent=4, cls=DataclassJSONEncoder)


def _extract_err_msg(episode_info: list[StepInfo]):
    """Extract the last error message from the episode info."""
    errors = [(None, None)]
    for step_info in episode_info:
        if step_info.agent_info is None:
            continue
        err_msg = step_info.agent_info.get("err_msg", None)
        if err_msg is not None:
            errors.append((err_msg, step_info.agent_info.get("stack_trace", None)))

    return errors[-1]


def _aggregate_episode_stats(episode_info: list[StepInfo]):
    """Aggregate StepInfo.stats across episodes.

    It will compute the sum and max of each value in the stats dict.
    These two summaries should cover many use cases. If more are needed, the
    user can compute other stats by reloading individual StepInfo.
    """

    stats = defaultdict(list)
    for step_info in episode_info:
        if step_info.stats is not None:
            for key, val in step_info.stats.items():
                if val is None:
                    val = np.nan
                stats[key].append(val)

    aggregated_stats = {"cum_steps": len(episode_info)}  # to be able to compute the mean
    for key, val_list in stats.items():
        aggregated_stats[f"cum_{key}"] = np.nansum(val_list)
        aggregated_stats[f"max_{key}"] = np.nanmax(val_list)

    for key, val in aggregated_stats.items():
        if isinstance(val, np.generic):
            aggregated_stats[key] = val.item()
        if np.isnan(val):
            aggregated_stats[key] = None
    return aggregated_stats


def _save_summary_info(
    episode_info: list[StepInfo],
    exp_dir,
    err_msg,
    stack_trace,
):
    # bring err from agent_info to the top level
    if err_msg is None:
        err_msg, stack_trace = _extract_err_msg(episode_info)
    else:
        # useful until we get a proper place in agent_xray to view error
        # messages.
        if len(episode_info) == 0:
            episode_info.append(StepInfo())
        episode_info[-1].agent_info["err_msg"] = err_msg
        episode_info[-1].agent_info["stack_trace"] = stack_trace

    summary_info = dict(
        n_steps=len(episode_info) - 1,
        cum_reward=sum([step.reward for step in episode_info]),
        cum_raw_reward=sum([step.raw_reward for step in episode_info if step.raw_reward]),
        err_msg=err_msg,
        stack_trace=stack_trace,
    )
    for key, val in _aggregate_episode_stats(episode_info).items():
        summary_info[f"stats.{key}"] = val

    # Separate steps into ID and OOD based on step number
    id_steps = [step for step in episode_info if step.step >= 0]
    ood_steps = [step for step in episode_info if step.step < 0]

    # Find the last step in ID steps and the first step in OOD steps
    if id_steps:
        id_last_step = max(id_steps, key=lambda step: step.step)
        summary_info["terminated"] = id_last_step.terminated
        summary_info["truncated"] = id_last_step.truncated
        summary_info["ood_detected_in_id"] = id_last_step.ood_detected

    if ood_steps:
        ood_last_step = min(ood_steps, key=lambda step: step.step)
        summary_info["ood_terminated"] = ood_last_step.terminated
        summary_info["ood_truncated"] = ood_last_step.truncated
        summary_info["ood_detected_in_ood"] = ood_last_step.ood_detected
        summary_info["ood_n_steps"] = len(ood_steps)
    else:  # if no ood steps, it means the ood is not triggered and LLM agents never make it to the ood step
        summary_info["ood_n_steps"] = 0  # so the ood_n_steps is 0 is a signal

    with open(exp_dir / "summary_info.json", "w") as f:
        json.dump(summary_info, f, indent=4)


def _is_debugging():
    """Tells you if your code is currently running in debug mode."""
    return sys.gettrace() is not None


class ExpResult:
    """Helper class to load and visualize the results of an experiment.

    attributes are loaded lazily.

    Attributes (lazily loaded):
        exp_args: ExpArgs, the arguments of the experiment.
        steps_info: list[StepInfo], the information of each steps so far
        summary_info: dict, the summary of the experiment.
        screenshots: list[Image], the screenshots of each step.
        screenshots_som: list[Image], the screenshots of each step with set of
            marks inprinted.
        flat_exp_args: dict, the flattened version of exp_args.
        chat_video_path: Path, the path to the chat video. (if record_video=True)
        task_video_path: Path, the path to the task video. (if record_video=True)
        combined_video_path: Path, the path to the combined video. (if video was
            combined)
    """

    def __init__(self, exp_dir) -> None:
        self.exp_dir = Path(exp_dir)
        self._exp_args = None
        self._steps_info = {}
        self._summary_info = None
        self._screenshots = {}
        self._flat_exp_args = None
        self._logs = None

    @property
    def exp_args(self) -> ExpArgs:
        if self._exp_args is None:
            with open(self.exp_dir / "exp_args.pkl", "rb") as f:
                self._exp_args = pickle.load(f)
                # in case experiments were moved
                self._exp_args.exp_dir = self.exp_dir
        return self._exp_args

    def get_step_info(self, step: int) -> StepInfo:
        """Load the step info from the file and return it."""
        if self._steps_info.get(step, None) is None:
            with gzip.open(self.exp_dir / f"step_{step}.pkl.gz", "rb") as f:
                self._steps_info[step] = pickle.load(f)
            if self._steps_info[step].obs:
                if "screenshot" not in self._steps_info[step].obs:
                    try:
                        self._steps_info[step].obs["screenshot"] = np.array(
                            self.get_screenshot(step), dtype=np.uint8
                        )
                    except FileNotFoundError:
                        pass
                if "screenshot_som" not in self._steps_info[step].obs:
                    try:
                        self._steps_info[step].obs["screenshot_som"] = np.array(
                            self.get_screenshot(step, som=True), dtype=np.uint8
                        )
                    except FileNotFoundError:
                        pass
                # if goal_object is set to None, it indicates it has been saved into a separate file
                if (
                    "goal_object" in self._steps_info[step].obs
                    and self._steps_info[step].obs["goal_object"] is None
                ):
                    with gzip.open(self.exp_dir / "goal_object.pkl.gz", "rb") as f:
                        goal_object = pickle.load(f)
                        self._steps_info[step].obs["goal_object"] = goal_object

        return self._steps_info[step]

    @property
    def steps_info(self) -> list[StepInfo]:
        step_files = list(self.exp_dir.glob("step_*.pkl.gz"))
        for file in step_files:
            step = int(file.name.split("_")[-1].split(".")[0])
            self.get_step_info(step)

        return [self._steps_info[i] for i in range(len(self._steps_info))]

    @property
    def summary_info(self) -> dict:
        if self._summary_info is None:
            with open(self.exp_dir / "summary_info.json", "r") as f:
                # if length is zero raise file not found error
                if os.fstat(f.fileno()).st_size == 0:
                    raise FileNotFoundError(f"summary_info.json is empty.")
                self._summary_info = json.load(f)
        return self._summary_info

    @property
    def tape(self) -> dict:
        """
        TapeAgents (https://github.com/ServiceNow/TapeAgents) framework compatibility.
        Exports experiment trace in the format of serialized tape.
        Reuses tape segments if they were already placed in the agent_info during the experiment.

        :returns: dict: serialized tape of the experiment
        """
        steps = []
        for step_info in self.steps_info:
            if "tape_segment" in step_info.agent_info["extra_info"]:
                tape_segment = step_info.agent_info["extra_info"]["tape_segment"]
            else:
                tape_segment = self._create_tape_segment(step_info)
            steps += tape_segment
        metadata = dict(
            id=str(uuid.uuid4()),
            author=f"browsergym_agent_[{self.exp_args.agent_args.agent_name}]",
            result=self.get_exp_record(),
        )
        return dict(steps=steps, metadata=metadata)

    def _create_tape_segment(self, step_info: StepInfo) -> list[dict]:
        tape_segment = []
        # extract observation step
        if step_info.obs is not None:
            screenshot: str = ""
            screenshot_som: str = ""
            obs_dict = copy.deepcopy(step_info.obs)
            if "screenshot" in obs_dict:
                screenshot = str(self.exp_dir / f"screenshot_step_{step_info.step}.png")
                obs_dict.pop("screenshot")
            if "screenshot_som" in obs_dict:
                screenshot_som = str(self.exp_dir / f"screenshot_som_step_{step_info.step}.png")
                obs_dict.pop("screenshot_som")
            tape_segment.append(
                dict(
                    kind="browsergym_observation",
                    metadata=dict(step=step_info.step),
                    obs=obs_dict,
                    screenshot=screenshot,
                    screenshot_som=screenshot_som,
                )
            )

        # extract thought step
        think = step_info.agent_info.get("think", "")
        if think:
            tape_segment.append(
                dict(kind="browsergym_thought", metadata={"step": step_info.step}, text=think)
            )

        # extract action steps
        function_calls = highlevel_action_parser.parse_string(step_info.action, parse_all=True)
        for name, arguments in function_calls:
            tape_segment.append(
                dict(
                    kind="browsergym_action",
                    metadata=dict(
                        step=step_info.step,
                        reward=step_info.reward,
                        raw_reward=step_info.raw_reward,
                        terminated=step_info.terminated,
                        truncated=step_info.truncated,
                        agent_info=step_info.agent_info,
                        stats=step_info.stats,
                        task_info=step_info.task_info,
                    ),
                    name=name,
                    arguments=arguments,
                )
            )
        return tape_segment

    def save_tape(self, filename: str = "tape.json"):
        if os.path.exists(self.exp_dir / filename):
            raise FileExistsError(f"{filename} already exists in {self.exp_dir}")
        with open(self.exp_dir / filename, "w") as f:
            json.dump(self.tape, f, indent=4, ensure_ascii=False)

    def get_screenshot(self, step: int, som=False) -> Image:
        key = (step, som)
        if self._screenshots.get(key, None) is None:
            file_name = f"screenshot_{'som_' if som else ''}step_{step}"
            try:
                with Image.open(self.exp_dir / (file_name + ".png")) as img:
                    self._screenshots[key] = img.copy()
            except FileNotFoundError:
                with Image.open(self.exp_dir / (file_name + ".jpg")) as img:
                    self._screenshots[key] = img.copy()
        return self._screenshots[key]

    def get_screenshots(self, som=False):
        files = list(self.exp_dir.glob("screenshot_step_*"))
        max_step = 0
        for file in files:
            step = int(file.name.split("_")[-1].split(".")[0])
            self.get_screenshot(step, som=som)
            max_step = max(max_step, step)
        return [self._screenshots.get((i, som), None) for i in range(max_step + 1)]

    @property
    def screenshots(self):
        return self.get_screenshots(som=False)

    @property
    def screenshots_som(self):
        return self.get_screenshots(som=True)

    @property
    def flat_exp_args(self) -> dict:
        """Return a dict with exp_args flattened."""
        if self._flat_exp_args is None:
            exp_args = asdict(self.exp_args)
            # this will flatten nested dicts
            self._flat_exp_args = _flatten_dict(exp_args)
        return self._flat_exp_args

    def get_exp_record(self) -> dict:
        """Return a dict with exp_args flattened and summary_info."""
        record = {"exp_dir": self.exp_dir}
        try:
            record.update(self.flat_exp_args)
        except FileNotFoundError:
            pass
        try:
            record.update(self.summary_info)
        except FileNotFoundError:
            pass
        return record

    @property
    def chat_video_path(self) -> Path:
        try:
            return next(self.exp_dir.glob("chat_video/*.webm"))
        except StopIteration:
            raise FileNotFoundError(f"No chat_video found in {self.exp_dir}")

    @property
    def task_video_path(self) -> Path:
        try:
            return next(self.exp_dir.glob("task_video/*.webm"))
        except StopIteration:
            raise FileNotFoundError(f"No task_video found in {self.exp_dir}")

    @property
    def combined_video_path(self) -> Path:
        return self.exp_dir / "combined_video.mp4"

    @property
    def logs(self):
        if self._logs is None:
            self._logs = (self.exp_dir / "experiment.log").read_text()
        return self._logs

    @property
    def status(self):
        """Return one of the following status:
        * "done": completed with no error
        * "error": completed with error
        * "incomplete": not completed yet (may be pending or just stalled)
        """
        try:
            summary_info = self.summary_info
        except FileNotFoundError:
            return "incomplete"

        if summary_info.get("err_msg", None) is not None:
            return "error"

        if summary_info.get("terminated", False) or summary_info.get("truncated", False):
            return "done"

        return "incomplete"


EXP_RESULT_CACHE = {}


def get_exp_result(exp_dir) -> ExpResult:
    """Keep a cache of pre-loaded exp_results for faster loading"""
    exp_dir = str(exp_dir)  # make sure it's not a Path
    exp_result = EXP_RESULT_CACHE.get(exp_dir, None)
    if exp_result is None:
        exp_result = ExpResult(exp_dir)
        EXP_RESULT_CACHE[exp_dir] = exp_result
    return exp_result


def yield_all_exp_results(
    savedir_base: str | Path, progress_fn=tqdm, load_hidden=False, use_cache=True
):
    """Recursively find all experiments from savedir_base folder.

    This will ignore all experiments that start with "_" or ".". use
    `load_hidden=True` to load them anyway.
    """

    if not isinstance(savedir_base, list):
        savedir_base = [savedir_base]

    exp_args_paths = []
    for exp_dir in savedir_base:
        exp_args_paths.extend(list(Path(exp_dir).glob("**/exp_args.pkl")))

    if progress_fn is not None:
        exp_args_paths = progress_fn(exp_args_paths, desc="Searching experiments directories.")

    for exp_args_path in exp_args_paths:
        exp_dir = exp_args_path.parent
        if not load_hidden:
            if exp_dir.name.startswith("_") or exp_dir.name.startswith("."):
                continue
        if use_cache:
            yield get_exp_result(exp_dir)
        else:
            yield ExpResult(exp_dir)


class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def _move_old_exp(exp_dir):
    """Move the old experiment directory to a new name."""
    exp_dir = Path(exp_dir)
    if exp_dir.exists():
        exp_dir.rename(exp_dir.with_name("_" + exp_dir.name))


def _get_env_name(task_name: str):
    """Register tasks if needed (lazy import) and return environment name."""

    # lazy benchmark import
    if task_name.startswith("miniwob"):
        import browsergym.miniwob
    elif task_name.startswith("workarena"):
        import browsergym.workarena
    elif task_name.startswith("webarena"):
        import browsergym.webarena
    elif task_name.startswith("visualwebarena"):
        import browsergym.visualwebarena
    elif task_name.startswith("assistantbench"):
        import browsergym.assistantbench
    elif task_name.startswith("weblinx"):
        import weblinx_browsergym
    elif task_name.startswith("oodarena"):
        import browsergym.oodarena

    return f"browsergym/{task_name}"


def _send_chat_info(chat: Chat, action: str, agent_info: dict):
    """Send the think and action info to the chat."""
    msg = ""
    if "think" in agent_info:
        msg += f"""\
{agent_info["think"]}

"""

    msg += f"""\
action:
{action}
"""

    logger.info(msg)
    chat.add_message(role="info", msg=msg)


def _flatten_dict(d, parent_key="", sep="."):
    """Recursively flatten a nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
