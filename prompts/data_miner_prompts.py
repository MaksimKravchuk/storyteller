"""Prompt templates for the Data Miner agent."""

from prompts.base_template import PromptSection, PromptTemplate

DATA_MINER_SYSTEM = PromptTemplate([
    PromptSection(
        name="role",
        template=(
            "You are a historical research specialist for an interactive "
            "text quest. Your job is to synthesise raw Wikipedia excerpts "
            "into a structured game setting. Be accurate to real history "
            "but fill in plausible details where sources are thin."
        ),
    ),
])


DATA_MINER_SEARCH_TERMS = PromptTemplate([
    PromptSection(
        name="task",
        template=(
            "The player wants a game setting based on:\n"
            '"{setting_request}"\n\n'
            "Generate a JSON list of 3-8 Wikipedia search terms that would "
            "give us the best historical context for this setting.\n"
            "Output ONLY a JSON object: "
            '{{"search_terms": ["term1", "term2", ...]}}'
        ),
        required_vars=["setting_request"],
    ),
])


DATA_MINER_RESEARCH = PromptTemplate([
    PromptSection(
        name="task",
        template=(
            "Setting request: {setting_request}\n\n"
            "Raw Wikipedia research:\n{raw_research}\n\n"
            "Synthesise this into a structured game setting. "
            "Output ONLY valid JSON with these fields:\n"
            '{{\n'
            '  "name": "Setting name",\n'
            '  "time_period": "e.g. 1st century AD",\n'
            '  "region": "e.g. Roman Empire, Italia",\n'
            '  "summary": "2-3 paragraph overview",\n'
            '  "key_persons": [{{"name": "...", "role": "...", "description": "..."}}],\n'
            '  "key_events": [{{"name": "...", "date": "...", "description": "..."}}],\n'
            '  "locations": [{{"name": "...", "type": "...", "description": "..."}}],\n'
            '  "traditions": ["..."],\n'
            '  "technologies": ["..."],\n'
            '  "social_structure": "Description of social hierarchy"\n'
            '}}'
        ),
        required_vars=["setting_request", "raw_research"],
    ),
])
