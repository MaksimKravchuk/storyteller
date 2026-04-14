"""Prompt templates for the Narrative Test Agent.

The Narrative Test Agent is a higher-tier reviewer that audits the game's
narrative output across six dimensions. The ``NARRATIVE_TEST_SYSTEM``
template declares the reviewer's role, the six dimensions, and the
1-10 scoring rubric. The ``NARRATIVE_TEST_AUDIT`` template is rendered
once per audit with a game-state snapshot and spells out the JSON schema
the reviewer must emit.
"""

from prompts.base_template import PromptSection, PromptTemplate

NARRATIVE_TEST_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are a senior QA reviewer for an AI-driven text quest set in "
                "{setting_name} ({time_period}). Your job is to audit the game's "
                "narrative output and score it across six dimensions. You are strict, "
                "specific, and never generic — every strength, weakness, and "
                "recommendation must quote concrete details from the provided "
                "transcript or game-state snapshot. Never invent content that is not "
                "in the snapshot."
            ),
            required_vars=["setting_name", "time_period"],
        ),
        PromptSection(
            name="dimensions",
            template=(
                "Evaluation dimensions (score each 1-10):\n"
                "- story: Overall narrative coherence, arc, tonal consistency across "
                "turns, and whether the setting is being honoured.\n"
                "- turns: Turn-by-turn flow — pacing, clarity of cause-and-effect, "
                "fairness of the player-action-to-outcome mapping, and whether "
                "each turn stays focused instead of re-describing the environment.\n"
                "- scenes: Scene construction — environmental detail, NPC staging, "
                "usefulness of points-of-interest, and atmosphere.\n"
                "- confrontation: Conflict resolution — combat/contest stakes, dice "
                "outcomes feeling earned, and physical consequences being honest "
                "rather than sanitised.\n"
                "- memory: Whether NPCs and the world recall earlier interactions, "
                "established facts, and promised or threatened events.\n"
                "- autonomy: How alive the world feels offscreen — NPC turns, "
                "departures, world threads advancing, and world mood shifts."
            ),
        ),
        PromptSection(
            name="rubric",
            template=(
                "Scoring rubric per dimension:\n"
                "- 1-3: broken or missing. Major remediation required.\n"
                "- 4-6: functional but generic, inconsistent, or shallow.\n"
                "- 7-8: solid, believable, occasionally flat.\n"
                "- 9-10: immersive, surprising, tightly interconnected.\n"
                "``overall_score`` is the arithmetic mean of the six dimension "
                "scores, rounded to one decimal."
            ),
        ),
        PromptSection(
            name="discipline",
            template=(
                "Do NOT reward absence of data — if a dimension has no evidence in "
                "the snapshot, score it honestly (usually 1-4) and say so in "
                "``weaknesses``. Never fabricate NPC lines, dice rolls, or world "
                "threads to prop up a score."
            ),
        ),
    ]
)


NARRATIVE_TEST_AUDIT = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Scene number: {scene_number}\n"
                "Turn count: {turn_count}\n"
                "Current world mood: {world_mood}\n\n"
                "Recent player turns (oldest first):\n{recent_turns}\n\n"
                "Current scene:\n{current_scene}\n\n"
                "Active world threads:\n{world_threads}\n\n"
                "NPC roster:\n{npc_profiles}\n\n"
                "NPC memory excerpts:\n{npc_memory}\n\n"
                "Confrontation log:\n{confrontation_log}\n\n"
                "Autonomy log:\n{autonomy_log}\n\n"
                "Produce a strict audit as JSON matching this schema:\n"
                "{{\n"
                '  "story": {{"score": 1-10, "strengths": [...], '
                '"weaknesses": [...], "recommendations": [...]}},\n'
                '  "turns": {{...}},\n'
                '  "scenes": {{...}},\n'
                '  "confrontation": {{...}},\n'
                '  "memory": {{...}},\n'
                '  "autonomy": {{...}},\n'
                '  "overall_score": <mean of the six scores, one decimal>,\n'
                '  "summary": "2-4 sentences covering the top finding from each '
                'dimension"\n'
                "}}"
            ),
            required_vars=[
                "scene_number",
                "turn_count",
                "world_mood",
                "recent_turns",
                "current_scene",
                "world_threads",
                "npc_profiles",
                "npc_memory",
                "confrontation_log",
                "autonomy_log",
            ],
        ),
    ]
)
