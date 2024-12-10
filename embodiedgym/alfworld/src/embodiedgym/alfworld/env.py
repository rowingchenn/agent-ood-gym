from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv


class SingleAlfredTWEnv(AlfredTWEnv):
    """
    Interface for Textworld Env
    Contains only one game_file per environment
    """

    def __init__(self, config, name, train_eval="eval_out_of_distribution"):
        print("Initializing AlfredTWEnv...")
        self.config = config
        self.train_eval = train_eval

        self.goal_desc_human_anns_prob = self.config["env"]["goal_desc_human_anns_prob"]
        self.get_game_logic()
        # self.gen_game_files(regen_game_files=self.config['env']['regen_game_files'])

        self.random_seed = 42

        self.game_files = [name]
        self.num_games = 1


def get_all_game_files(config, split="eval_out_of_distribution"):
    env = AlfredTWEnv(config, train_eval=split)
    game_files = env.game_files
    del env
    return game_files
