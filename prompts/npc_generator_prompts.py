"""Prompt templates for the NPC Generator agent."""

from prompts.base_template import PromptSection, PromptTemplate

NPC_GENERATOR_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are an NPC Generator for an interactive text quest. "
                "You create detailed, historically plausible character cards. "
                "Each NPC should feel like a real person with their own life, "
                "goals, and limitations — not a plot device."
            ),
        ),
        PromptSection(
            name="setting",
            template=("Setting: {setting_summary}\nLocation: {location_name}\nSocial structure: {social_structure}"),
            required_vars=["setting_summary", "location_name", "social_structure"],
        ),
    ]
)


NPC_GENERATOR_CREATE = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Create an NPC: {npc_request}\n\n"
                "Output ONLY valid JSON with these fields:\n"
                "{{\n"
                '  "name": "A historically appropriate name",\n'
                '  "biography": "2-3 sentences of backstory",\n'
                '  "appearance": "Physical description, clothing, distinguishing features",\n'
                '  "occupation": "Their trade or role",\n'
                '  "personality_traits": ["trait1", "trait2", "trait3"],\n'
                '  "speech_style": "How they talk — formal, crude, scholarly, etc.",\n'
                '  "knowledge_scope": "local|city|region|country|world",\n'
                '  "attributes": {{\n'
                '    "education": 0-10,\n'
                '    "social_status": 0-10,\n'
                '    "friendliness": 0-10,\n'
                '    "suspicion": 0-10,\n'
                '    "combat_skill": 0-10  // 0=helpless, 3=average, 7=trained soldier, 10=elite warrior\n'
                "  }},\n"
                '  "inventory": ["items they carry or sell"]\n'
                "}}"
            ),
            required_vars=["npc_request"],
        ),
    ]
)
