from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptSection:
    """A named, reusable block of prompt text.

    ``template`` uses Python str.format() placeholders, e.g. ``{setting_name}``.
    ``required_vars`` lists the placeholder names this section needs.
    """
    name: str
    template: str
    required_vars: list[str] = field(default_factory=list)

    def render(self, **kwargs: str) -> str:
        missing = [v for v in self.required_vars if v not in kwargs]
        if missing:
            raise ValueError(
                f"Missing template variables for section '{self.name}': {missing}"
            )
        return self.template.format(**kwargs)


class PromptTemplate:
    """Composable prompt built from ordered sections.

    Sections whose required variables are all present are rendered and joined.
    Sections with missing variables are silently skipped, making the template
    adapt to partial context (e.g. no scene info on the first turn).
    """

    def __init__(
        self,
        sections: list[PromptSection] | None = None,
        separator: str = "\n\n",
    ):
        self._sections: list[PromptSection] = list(sections or [])
        self._separator = separator

    def add_section(self, section: PromptSection) -> PromptTemplate:
        """Append a section. Returns ``self`` for fluent chaining."""
        self._sections.append(section)
        return self

    def render(self, **kwargs: str) -> str:
        """Render all sections whose required vars are satisfied."""
        parts: list[str] = []
        for section in self._sections:
            if all(v in kwargs for v in section.required_vars):
                parts.append(section.render(**kwargs))
        return self._separator.join(parts)

    @property
    def required_vars(self) -> set[str]:
        """Union of all required vars across every section."""
        result: set[str] = set()
        for s in self._sections:
            result.update(s.required_vars)
        return result

    def __repr__(self) -> str:
        names = [s.name for s in self._sections]
        return f"PromptTemplate(sections={names})"
