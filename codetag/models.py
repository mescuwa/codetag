"""Central data models for CodeTag using Pydantic.

Defining all data structures in one place prevents circular dependencies
and ensures a single source of truth for the application's data shapes.
"""

import time
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .fs_tree import FsNode


# --- Core Analysis Models -------------------------------------------------

class AnalysisMetadata(BaseModel):
    report_version: str = "1.1"
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    analysis_duration_seconds: float


class RepositorySummary(BaseModel):
    total_files: int = 0
    total_lines_of_code: int = 0
    primary_language: Optional[str] = None
    language_stats: Dict[str, int] = Field(default_factory=dict)
    total_functions_found: int = 0
    average_cyclomatic_complexity: float = 0.0


class LargestFile(BaseModel):
    path: str
    size_bytes: int
    is_lfs: Optional[bool] = None


class KeyFiles(BaseModel):
    largest_files: List[LargestFile] = Field(default_factory=list)
    important_files_detected: List[str] = Field(default_factory=list)


class ComplexFunction(BaseModel):
    file_path: str
    function_name: str
    line_number: int
    complexity_score: int


class CodeInsights(BaseModel):
    todo_count: int = 0
    fixme_count: int = 0
    top_complex_functions: List[ComplexFunction] = Field(default_factory=list)


class DependencyInfo(BaseModel):
    dependency_files_found: Dict[str, List[str]] = Field(default_factory=dict)


# --- Security & Threat Models --------------------------------------------

class FoundSecretModel(BaseModel):
    file_path: str
    secret_type: str
    line_number: int
    line_content: str


class DependencyVulnerability(BaseModel):
    id: str
    package_name: str
    vulnerable_version: str
    summary: str
    severity: Optional[str] = None


class CodeVulnerability(BaseModel):
    check_id: str
    path: str
    line: int
    message: str
    severity: str


class ThreatAssessment(BaseModel):
    dependency_vulnerabilities: List[DependencyVulnerability] = Field(default_factory=list)
    code_vulnerabilities: List[CodeVulnerability] = Field(default_factory=list)
    secrets_found: List[FoundSecretModel] = Field(default_factory=list)


# --- Top-Level Report Model ----------------------------------------------

class AnalysisReport(BaseModel):
    analysis_metadata: AnalysisMetadata
    repository_summary: RepositorySummary
    directory_tree: List[FsNode]
    key_files: KeyFiles = Field(default_factory=KeyFiles)
    code_insights: CodeInsights = Field(default_factory=CodeInsights)
    dependency_info: DependencyInfo = Field(default_factory=DependencyInfo)
    threat_assessment: ThreatAssessment = Field(default_factory=ThreatAssessment) 