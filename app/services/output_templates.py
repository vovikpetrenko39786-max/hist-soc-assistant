from dataclasses import dataclass


@dataclass(frozen=True)
class OutputTemplate:
    name: str
    version: str
    font_name: str
    title_size_pt: int
    heading_size_pt: int
    body_size_pt: int
    small_size_pt: int
    margin_cm: float
    compact: bool = False


class OutputTemplateRegistry:
    _templates = {
        "school_clean": OutputTemplate(
            name="school_clean",
            version="1.1",
            font_name="Liberation Sans",
            title_size_pt=18,
            heading_size_pt=12,
            body_size_pt=10,
            small_size_pt=8,
            margin_cm=1.7,
            compact=False,
        ),
        "compact_print": OutputTemplate(
            name="compact_print",
            version="1.0",
            font_name="Liberation Sans",
            title_size_pt=15,
            heading_size_pt=11,
            body_size_pt=9,
            small_size_pt=7,
            margin_cm=1.3,
            compact=True,
        ),
    }

    @classmethod
    def get(cls, name: str) -> OutputTemplate:
        try:
            return cls._templates[name]
        except KeyError as exc:
            raise ValueError(
                f"Unknown output template '{name}'. Available: {', '.join(cls._templates)}"
            ) from exc

    @classmethod
    def names(cls) -> list[str]:
        return sorted(cls._templates)
