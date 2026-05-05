"""Canonical concept slugs the AnachronismClassifier prefers when tagging.

Pinning the LLM to a stable vocabulary is a precondition for the
familiarity-discount loop in :mod:`cast.anachronism`. Without it, two
classifier calls on the same concept would emit
``light_without_flame`` and ``cold_light``, the per-NPC encounter
counter would never match across turns, and the discount would be
dead code. The fuzzy-match cushion in
:func:`knowledge.query_filters.concept_tag_matches` covers token-level
drift (``flame`` vs ``fire``) but not category-level drift, hence
this list.

Slugs are snake_case. Keep them noun-shaped — they describe the
*phenomenon* an in-period NPC would witness, not the device. A
witness sees ``light_without_flame`` when the player thumbs on a
phone torch; calling the slug ``smartphone_flashlight`` would couple
the tag to one specific gadget and miss every other LED source.
"""

from __future__ import annotations

# Tuple (not list) so a callsite can't accidentally mutate the seed
# pool and silently change the classifier's vocabulary mid-session.
ANACHRONISM_CONCEPT_SEEDS: tuple[str, ...] = (
    "light_without_flame",
    "cold_glow",
    "voice_from_afar",
    "image_capture",
    "moving_picture",
    "soul_binding_via_image",
    "metal_carriage",
    "horseless_wagon",
    "iron_bird",
    "self_propelled_boat",
    "talking_box",
    "writing_that_speaks",
    "knowledge_machine",
    "thinking_engine",
    "lightning_in_a_jar",
    "thunder_stick",
    "fire_at_a_distance",
    "instant_messaging_charm",
    "self_writing_letter",
    "miniature_mirror_that_remembers",
    "warmth_without_hearth",
    "cold_storage_chest",
    "music_without_musicians",
    "invisible_messenger",
    "map_that_speaks",
    "self_lighting_lantern",
    "garments_of_the_far_north",
    "incomprehensible_foreign_learning",
    "claim_of_godly_power",
    "claim_of_demonic_pact",
)
