from dataclasses import dataclass, field
from typing import List


@dataclass
class IssueData:
    title: str
    body: str
    labels: List[str]
    comments: List[str]


@dataclass
class CodeChunk:
    path: str
    text: str
    score: float = 0.0


@dataclass
class IssueAnalysis:
    problem_summary: str
    possible_root_causes: List[str]
    files_to_modify: List[str]
    implementation_steps: List[str]
    testing_strategy: str


@dataclass
class FilePatch:
    path: str
    old_code: str
    new_code: str


@dataclass
class FixResult:
    explanation: str
    risks: List[str]
    patches: List[FilePatch] = field(default_factory=list)


@dataclass
class ValidationResult:
    passed: bool
    stdout: str
    stderr: str


@dataclass
class PullRequestSummary:
    title: str
    description: str
