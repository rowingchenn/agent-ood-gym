# from dataclasses import dataclass


# ACTION_SUBSETS = {
#     "infeasible": "",
#     "alfworld": "",
# }


# class HighLevelActionSet:
#     """
#     Attributes:
#         subsets: Available action subsets.
#         custom_actions: Custom actions.
#         strict: Whether to enforce strict action parsing.
#         retry_with_force: Whether to retry
#     """


# @dataclass
# class HighLevelActionSetArgs:
#     """
#     Attributes:
#         subsets: Available action subsets.
#         strict: Whether to enforce strict action parsing.

#     """

#     subsets: tuple[HighLevelActionSet.ActionSubset]
#     strict: bool = False

#     def __post_init__(self):
#         if isinstance(self.subsets, list):
#             """Needs to be hashable for AgentLab when uniquely identifying agents."""
#             self.subsets = tuple(self.subsets)

#     def make_action_set(self):
#         return HighLevelActionSet(
#             subsets=self.subsets,
#             custom_actions=None,
#             multiaction=self.multiaction,
#             strict=self.strict,
#             retry_with_force=self.retry_with_force,
#             demo_mode=self.demo_mode,
#         )
