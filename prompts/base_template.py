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
        missing = [required_var for required_var in self.required_vars if required_var not in kwargs]
        if missing:
            raise ValueError(f"Missing template variables for section '{self.name}': {missing}")
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
            if all(required_var in kwargs for required_var in section.required_vars):
                parts.append(section.render(**kwargs))
        return self._separator.join(parts)

    @property
    def required_vars(self) -> set[str]:
        """Union of all required vars across every section."""
        all_vars: set[str] = set()
        for section in self._sections:
            all_vars.update(section.required_vars)
        return all_vars

    @property
    def sections(self) -> tuple[PromptSection, ...]:
        """Read-only snapshot of the ordered section list for introspection."""
        return tuple(self._sections)

    def __repr__(self) -> str:
        names = [section.name for section in self._sections]
        return f"PromptTemplate(sections={names})"
