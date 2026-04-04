"""Prompt templates for the Item Generator agent."""

from prompts.base_template import PromptSection, PromptTemplate

ITEM_GENERATOR_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are an Item Generator for an interactive text quest. "
                "You produce precise, physical descriptions of objects — weapons, tools, "
                "goods, clothing, containers, and other items.\n"
                "STRICT RULES:\n"
                "- Describe ONLY physical properties: material, dimensions, weight, "
                "condition, wear marks, construction method.\n"
                "- NO literary flourishes. NO 'beautifully crafted', 'gleaming in the light', "
                "'ornately decorated'. State facts.\n"
                "- NO backstory or history unless explicitly requested.\n"
                "- Use period-appropriate terminology for the setting.\n"
                "- Format each item as: Name (material, key dimensions, condition, notable features)."
            ),
        ),
        PromptSection(
            name="setting",
            template="Setting: {setting_summary}",
            required_vars=["setting_summary"],
        ),
    ]
)


ITEM_GENERATOR_BATCH = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Expand these bare item names into precise physical descriptions.\n"
                "Owner context: {owner_context}\n\n"
                "Items to describe:\n{item_list}\n\n"
                "Output ONLY valid JSON:\n"
                "{{\n"
                '  "items": [\n'
                '    "ItemName (material, dimensions, condition, features)",\n'
                '    "...one entry per input item, same order..."\n'
                "  ]\n"
                "}}\n\n"
                "Keep each description under 120 characters. Be factual and specific."
            ),
            required_vars=["owner_context", "item_list"],
        ),
    ]
)


ITEM_GENERATOR_EXAMINE = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Produce a detailed physical examination of this item.\n"
                "Item: {item_name}\n"
                "Context: {context_hint}\n\n"
                "Output ONLY valid JSON:\n"
                "{{\n"
                '  "description": "Detailed physical description: material, construction, '
                'dimensions, weight estimate, condition, wear patterns, maker marks if visible."\n'
                "}}\n\n"
                "Be precise and factual. 2-4 sentences maximum."
            ),
            required_vars=["item_name", "context_hint"],
        ),
    ]
)
