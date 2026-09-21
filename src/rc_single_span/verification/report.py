from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalculationStep:
    title: str
    formula: str
    substitution: str
    result: str
    reference: str
    status: str = ""

    def __post_init__(self) -> None:
        for value, label in (
            (self.title, "title"),
            (self.formula, "formula"),
            (self.substitution, "substitution"),
            (self.result, "result"),
            (self.reference, "reference"),
        ):
            if not value.strip():
                raise ValueError(f"Calculation step {label} cannot be empty.")


@dataclass(frozen=True)
class CalculationSection:
    title: str
    steps: tuple[CalculationStep, ...]
    note: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Calculation section title cannot be empty.")
        if not self.steps:
            raise ValueError("Calculation section requires at least one step.")


@dataclass(frozen=True)
class CalculationReport:
    title: str
    project_name: str
    sections: tuple[CalculationSection, ...]
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.project_name.strip():
            raise ValueError("Calculation report title and project name are required.")
        if not self.sections:
            raise ValueError("Calculation report requires at least one section.")


def render_markdown(report: CalculationReport) -> str:
    """Render a deterministic engineering calculation report in Markdown."""

    lines = [
        f"# {report.title}",
        "",
        f"**Project:** {report.project_name}",
        "",
    ]
    if report.assumptions:
        lines.extend(("## Assumptions", ""))
        lines.extend(f"- {item}" for item in report.assumptions)
        lines.append("")
    if report.warnings:
        lines.extend(("## Warnings / review items", ""))
        lines.extend(f"- {item}" for item in report.warnings)
        lines.append("")

    for section in report.sections:
        lines.extend((f"## {section.title}", ""))
        if section.note:
            lines.extend((section.note, ""))
        for index, step in enumerate(section.steps, start=1):
            lines.extend(
                (
                    f"### {index}. {step.title}",
                    "",
                    f"**Formula:** {step.formula}",
                    "",
                    f"**Substitution:** {step.substitution}",
                    "",
                    f"**Result:** {step.result}",
                    "",
                    f"**Reference:** {step.reference}",
                    "",
                )
            )
            if step.status:
                lines.extend((f"**Status:** {step.status}", ""))
    return "\n".join(lines).rstrip() + "\n"
