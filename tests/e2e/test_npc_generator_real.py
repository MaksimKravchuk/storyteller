"""Real-model NPCGenerator smoke tests.

The NPC Generator takes a list of role descriptions and returns
:class:`models.npc_card.NPCCard` instances. Each test asks for one role,
checks the returned card honours the requested role (input-tied) and
satisfies the basic schema contract.
"""

from __future__ import annotations

import allure
import pytest

from cast.npc_generator import NPCGenerator
from models.npc_card import NPCCard
from tests import director_helpers
from tests.e2e._real_llm import real_llm_for

# Ways a model names a messenger without the word: gpt-6-luna billed the
# requested wounded messenger as a "Letter-carrier" who was "carrying letters".
_MESSENGER_SYNONYMS = (
    "messenger",
    "courier",
    "herald",
    "runner",
    "envoy",
    "rider",
    "letter-carrier",
    "letter carrier",
    "carrying letters",
    "carries letters",
    "dispatch",
)

# Ways a model writes "blind" without the word: gpt-6-luna described the
# requested blind beggar as having "cloudy eyes" and having "lost his sight".
_BLINDNESS_MARKERS = (
    "blind",
    "sightless",
    "unseeing",
    "milky eyes",
    "clouded eyes",
    "cloudy eyes",
    "lost his sight",
    "lost her sight",
    "lost their sight",
)


@allure.epic("AI Agent Orchestration")
@allure.feature("NPCGenerator real-model materialisation")
class TestNPCGeneratorRealModel:
    @allure.story("Requested role surfaces in occupation")
    @allure.title("A real NPCGenerator model honours a distinctive role request")
    @pytest.mark.asyncio
    async def test_real_model_honours_requested_role(self):
        game_state = director_helpers.make_game_state()
        generator = NPCGenerator(llm_client=real_llm_for("npc_generator"), language="English")

        cards = await generator.act(["wounded messenger"], {"game_state": game_state})

        assert len(cards) == 1, "Expected exactly one NPC for one requested role"
        card = cards[0]
        assert isinstance(card, NPCCard)
        # Input-tied: the requested role must surface somewhere on the
        # card. "messenger" has a few period-appropriate synonyms
        # (courier, herald, letter-carrier, …) the model legitimately picks
        # — accept any of them — but reject a card that is silent on
        # the role across occupation, short_descriptor, and biography.
        # Failure mode this catches: role list dropped from the prompt
        # body, or the LLM returning an arbitrary persona.
        haystack = " ".join((card.occupation, card.short_descriptor, card.biography)).lower()
        assert any(token in haystack for token in _MESSENGER_SYNONYMS), (
            "NPC for 'wounded messenger' has no messenger-synonym anywhere on the card.\n"
            "occupation={0!r}\nshort_descriptor={1!r}\nbiography={2!r}".format(
                card.occupation,
                card.short_descriptor,
                card.biography,
            )
        )
        # Schema contract: a non-empty name and a non-empty biography.
        assert card.name.strip(), "NPC has empty name"
        assert card.biography.strip(), "NPC has empty biography"

    @allure.story("Distinctive physical role survives generation")
    @allure.title("A real NPCGenerator carries a 'blind beggar' marker into appearance or descriptor")
    @pytest.mark.asyncio
    async def test_real_model_preserves_physical_marker(self):
        game_state = director_helpers.make_game_state()
        generator = NPCGenerator(llm_client=real_llm_for("npc_generator"), language="English")

        cards = await generator.act(["blind beggar"], {"game_state": game_state})

        assert len(cards) == 1
        card = cards[0]
        assert isinstance(card, NPCCard)
        assert "beggar" in card.occupation.lower(), (
            "NPCCard.occupation {0!r} does not contain requested role 'beggar'".format(card.occupation)
        )
        # Input-tied: 'blind' is the distinctive physical marker. A
        # well-grounded persona surfaces it in either ``appearance`` or
        # ``short_descriptor`` (the fall-back the alias resolver renders
        # for unintroduced NPCs).
        haystack = " ".join((card.appearance, card.short_descriptor, card.biography)).lower()
        assert any(marker in haystack for marker in _BLINDNESS_MARKERS), (
            "NPC for 'blind beggar' has no blindness marker in appearance/descriptor/biography.\n"
            "appearance={0!r}\nshort_descriptor={1!r}\nbiography={2!r}".format(
                card.appearance,
                card.short_descriptor,
                card.biography,
            )
        )
