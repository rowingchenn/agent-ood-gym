import gymnasium as gym
import browsergym.core  # register the openended task as a gym environment

# start an openended task
env = gym.make(
    "browsergym/openended",
    task_kwargs={"start_url": "https://www.google.com/"},  # starting URL
    wait_for_user_message=True,  # wait for a user message after each agent message sent to the chat
)
obs, info = env.reset()

print(obs)