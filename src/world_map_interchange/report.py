from __future__ import annotations

from dataclasses import asdict, dataclass, field

REPORT_VERSION = "0.1.0"


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    location: str | None = None
    file: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def render(self) -> str:
        where = []
        if self.file:
            where.append(self.file)
        if self.location:
            where.append(self.location)
        suffix = f" ({', '.join(where)})" if where else ""
        return f"{self.severity.upper():7} [{self.code}] {self.message}{suffix}"


@dataclass
class LayerSupport:
    id: str
    kind: str
    quantity: str | None
    status: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    target: str
    container: str | None = None
    format_version: str | None = None
    issues: list[Issue] = field(default_factory=list)
    checks: dict[str, str] = field(default_factory=dict)
    layers: list[LayerSupport] = field(default_factory=list)
    consumer: dict | None = None

    def add(self, severity: str, code: str, message: str, location: str | None = None, file: str | None = None) -> None:
        self.issues.append(Issue(severity, code, message, location, file))

    def error(self, code, message, location=None, file=None):
        self.add("error", code, message, location, file)

    def warning(self, code, message, location=None, file=None):
        self.add("warning", code, message, location, file)

    def info(self, code, message, location=None, file=None):
        self.add("info", code, message, location, file)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def conformant(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {i.code for i in self.errors}

    def to_dict(self) -> dict:
        return {
            "report_version": REPORT_VERSION,
            "target": self.target,
            "container": self.container,
            "format_version": self.format_version,
            "conformant": self.conformant,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "checks": self.checks,
            "issues": [i.to_dict() for i in self.issues],
            "layers": [layer.to_dict() for layer in self.layers],
            "consumer": self.consumer,
        }
