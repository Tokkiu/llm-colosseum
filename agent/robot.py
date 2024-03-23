import abc
from typing import List, Optional, Literal
from gymnasium import spaces
from loguru import logger

from .observer import detect_position_from_color, KEN_RED, KEN_GREEN
from .actions import get_actions_from_llm

from .config import MOVES, INDEX_TO_MOVE


class Robot:
    observations: List[Optional[dict]] = None  # memory
    next_steps: List[int]  # action plan
    actions: dict  # actions of the agents during a step of the game

    action_space: spaces.Space
    character: Optional[str] = None  # character name
    side: int  # side of the stage where playing: 0 = left, 1 = right
    current_direction: Literal["Left", "Right"]  # current direction facing

    def __init__(
        self,
        action_space: spaces.Space,
        character: str,
        side: int,
        character_color: list,
        ennemy_color: list,
    ):
        self.action_space = action_space
        self.character = character
        if side == 0:
            self.current_direction = "Right"
        elif side == 1:
            self.current_direction = "Left"

        self.observations = []
        self.next_steps = []
        self.character_color = character_color
        self.ennemy_color = ennemy_color
        self.side = side

    def act(self) -> int:
        """
        At each game frame, we execute the first action in the list of next steps.

        An action is an integer from 0 to 18, where 0 is no action.

        See the MOVES dictionary for the mapping of actions to moves.
        """
        if not self.next_steps or len(self.next_steps) == 0:
            return 0  # No move

        next_step = self.next_steps.pop(0)

        # Keep track of the current direction
        if "Left" in INDEX_TO_MOVE[next_step]:
            self.current_direction = "Left"
        elif "Right" in INDEX_TO_MOVE[next_step]:
            self.current_direction = "Right"

        return next_step

    def plan(self) -> None:
        """
        The robot will plan its next steps by calling this method.

        In SF3, moves are based on combos, which are list of actions that must be executed in a sequence.

        Moves of Ken
        https://www.eventhubs.com/guides/2009/may/11/ken-street-fighter-3-third-strike-character-guide/

        Moves of Ryu
        https://www.eventhubs.com/guides/2008/may/09/ryu-street-fighter-3-third-strike-character-guide/
        """

        # Detect own position
        own_position = self.observations[-1]["character_position"]
        ennemy_position = self.observations[-1]["ennemy_position"]

        # Note: at the beginning of the game, the position is None

        # If we already have a next step, we don't need to plan
        if len(self.next_steps) > 0:
            return

        # Get the context
        context = self.context_prompt()

        logger.debug(f"Context: {context}")

        # Call the LLM to get the next steps
        next_steps_from_llm = get_actions_from_llm(context, self.character)

        self.next_steps.extend(next_steps_from_llm)

        # Do a Hadouken
        # if self.current_direction == "Right":
        #     self.next_steps.extend(
        #         [
        #             MOVES["Down"],
        #             MOVES["Right+Down"],
        #             MOVES["Right"],
        #             MOVES["High Punch"],
        #         ]
        #     )
        # elif self.current_direction == "Left":
        #     self.next_steps.extend(
        #         [
        #             MOVES["Down"],
        #             MOVES["Down+Left"],
        #             MOVES["Left"],
        #             MOVES["High Punch"],
        #         ]
        #     )

    def observe(self, observation: dict, actions: dict):
        """
        The robot will observe the environment by calling this method.

        The latest observations are at the end of the list.
        """

        # detect the position of characters and ennemy based on color
        observation["character_position"] = detect_position_from_color(
            observation, self.character_color
        )
        observation["ennemy_position"] = detect_position_from_color(
            observation, self.ennemy_color
        )

        self.observations.append(observation)
        # we delete the oldest observation if we have more than 10 observations
        if len(self.observations) > 10:
            self.observations.pop(0)

        self.actions = actions

    def context_prompt(self):
        """
        Return a str of the context

        "The observation for you is Left"
        "The observation for the opponent is Left+Up"
        "The action history is Up"
        """
        side = self.side
        obs_own = self.observations[-1]["character_position"]
        obs_opp = self.observations[-1]["ennemy_position"]

        # Handle the first observation setting, if self.actions == {}
        if self.actions == {}:
            return f"""
            It's the first observation of the game, the game just started.
            The observation for you is {obs_own}
            The observation for the opponent is {obs_opp}
            """

        act_own = self.actions["agent_" + str(side)]
        act_opp = self.actions["agent_" + str(abs(1 - side))]
        str_act_own = INDEX_TO_MOVE[act_own]
        str_act_opp = INDEX_TO_MOVE[act_opp]

        context = f"""
        Your last action was {str_act_own}
        The opponent's last action was {str_act_opp}
        The opponent location is {obs_opp}
        Your position is {obs_own} 
        """

        logger.debug(f"Context: {context}")
        return context
