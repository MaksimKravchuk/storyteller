"""Helpers for projecting :class:`models.game_state.PlayerState` into prompt context."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

_DEFAULT_APPEARANCE = "unremarkable"
_DEFAULT_INVENTORY = "nothing of note"

# Verb mapping for :class:`PlayerUtterance`. The action_type strings come
# from the router's plan and from :class:`models.scene_action_log.SceneActionEntry`
# entries appended for player actions; unknown values fall through to the
# generic ``does`` verb so a prompt is always produced.
_VERB_BY_ACTION_TYPE: MappingProxyType[str, str] = MappingProxyType(
    {
        "TALK": "says",
        "ATTACK": "attacks",
        "INTIMIDATE": "snarls",
        "PERSUADE": "urges",
        "DECEIVE": "claims",
        "STEALTH": "slips through, doing",
        "EXPLORE": "looks around, doing",
        "LOOK": "looks around, doing",
        "MOVE": "moves, doing",
        "IDLE": "does",
        "PLAYER_INPUT": "does",
    },
)
_DEFAULT_VERB = "does"

# Verbs whose ``text`` should be quoted as direct speech in the rendered
# sentence. Anything else is rendered as a description.
_SPEECH_VERBS: frozenset[str] = frozenset(("says", "snarls", "urges", "claims"))


def format_player_appearance(player: Any) -> str:
    """Return appearance or a fallback so the player_character PromptSection always renders.

    Never returns ``None``. ``cast.scene_log.render_scene_log_entry_body``
    relies on this: a ``None`` here would silently route a player entry
    to the bare ``speaker: desc`` fallback in the NPC prompt.
    """
    return player.appearance or _DEFAULT_APPEARANCE


def is_default_appearance(appearance: str) -> bool:
    """True when *appearance* is the uninformative placeholder fallback."""
    return appearance == _DEFAULT_APPEARANCE


def format_player_inventory(player: Any) -> str:
    """Return inventory comma-joined or a fallback so the PromptSection always renders."""
    if not player.inventory:
        return _DEFAULT_INVENTORY
    return ", ".join(player.inventory)


@dataclass(frozen=True)
class PlayerUtterance:
    """Literary rendering of a player action.

    Single source of truth for how a player action is shown to NPCs:
    the per-turn ``Recent events:`` line, the rendered ``THIS SCENE
    SO FAR:`` clause, and the summariser transcript at scene end all
    funnel through :meth:`render`. Bundling appearance directly into
    the verb sentence ("The 190 cm Slav in dark furs says: ...") gives
    the LLM the player's identity in the same place it sees the
    action, instead of as a separate form field. The descriptor is a
    gender-neutral noun phrase ("The {appearance}"), not "A {appearance}
    man" — the player's gender is unknown here.

    When ``appearance`` is the :data:`_DEFAULT_APPEARANCE` placeholder
    the descriptor is dropped — there is no value in saying "the
    unremarkable one" — and the sentence falls back to ``Player
    {verb}: {text}``.
    """

    appearance: str
    action_type: str
    text: str

    def render(self) -> str:
        """Return the literary sentence for this utterance."""
        verb = _VERB_BY_ACTION_TYPE.get(self.action_type.upper(), _DEFAULT_VERB)
        body = '"{0}"'.format(self.text) if verb in _SPEECH_VERBS else self.text
        if self.appearance and self.appearance != _DEFAULT_APPEARANCE:
            return "The {0} {1}: {2}".format(self.appearance, verb, body)
        return "Player {0}: {1}".format(verb, body)


def render_player_entry(action_type: str, description: str, appearance: str) -> str:
    """Render a player scene-log entry through :class:`PlayerUtterance`.

    Single source of truth shared by :mod:`cast.npc_turn` (rendered
    scene history clause) and :mod:`knowledge.scene_consolidation`
    (summariser transcript) so the literary form stays consistent
    across surfaces.
    """
    return PlayerUtterance(appearance=appearance, action_type=action_type, text=description).render()
