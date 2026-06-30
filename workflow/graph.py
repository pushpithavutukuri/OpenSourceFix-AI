from typing import TypedDict

from langgraph.graph import StateGraph, END

from workflow.nodes import (
    repository_node,
    issue_node,
    retrieval_node,
    localization_node,
    fix_generation_node,
    validation_node,
    pr_node
)


class AgentState(TypedDict):

    repo_url: str

    repo_path: str

    issue: str

    repo_metadata: dict

    parsed_issue: dict

    retrieved_files: list

    suspect_files: list

    patch: dict

    validation: dict

    pr_summary: str


def build_graph():

    workflow = StateGraph(AgentState)

    workflow.add_node(
        "repository_analysis",
        repository_node
    )

    workflow.add_node(
        "issue_analysis",
        issue_node
    )

    workflow.add_node(
        "retrieval",
        retrieval_node
    )

    workflow.add_node(
        "bug_localization",
        localization_node
    )

    workflow.add_node(
        "fix_generation",
        fix_generation_node
    )

    workflow.add_node(
        "validation",
        validation_node
    )

    workflow.add_node(
        "pr_generator",
        pr_node
    )

    workflow.set_entry_point(
        "repository_analysis"
    )

    workflow.add_edge(
        "repository_analysis",
        "issue_analysis"
    )

    workflow.add_edge(
        "issue_analysis",
        "retrieval"
    )

    workflow.add_edge(
        "retrieval",
        "bug_localization"
    )

    workflow.add_edge(
        "bug_localization",
        "fix_generation"
    )

    workflow.add_edge(
        "fix_generation",
        "validation"
    )

    workflow.add_edge(
        "validation",
        "pr_generator"
    )

    workflow.add_edge(
        "pr_generator",
        END
    )

    return workflow.compile()
