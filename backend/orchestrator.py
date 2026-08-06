from github.github_issue import GitHubIssueFetcher

from agents.issue_analyzer import IssueAnalyzer
from agents.fix_generator import FixGenerator
from agents.validator import ValidationAgent
from agents.pr_generator import PRGenerator

from retrieval.retrieve import retrieve_relevant_chunks

from models.schemas import (
    IssueData,
    IssueAnalysis,
    ValidationResult
)


class OpenSourceFixAgent:

    def __init__(self):

        self.github = GitHubIssueFetcher()

        self.analyzer = IssueAnalyzer()

        self.fix_generator = FixGenerator()

        self.validator = ValidationAgent()

        self.pr_generator = PRGenerator()

    def run(
        self,
        repo_url,
        issue_number,
        repo_path
    ):

        print("\nFetching GitHub Issue...\n")

        issue = self.github.fetch_issue(
            repo_url,
            issue_number
        )

        issue_data = IssueData(

            title=issue["title"],

            body=issue["body"],

            labels=issue["labels"],

            comments=issue["comments"]

        )

        print("Issue fetched.")

        print("\nAnalyzing Issue...\n")

        analysis = self.analyzer.analyze(
            issue
        )

        analysis = IssueAnalysis(

            problem_summary=analysis[
                "problem_summary"
            ],

            possible_root_causes=analysis[
                "possible_root_causes"
            ],

            files_to_modify=analysis[
                "files_to_modify"
            ],

            implementation_steps=analysis[
                "implementation_steps"
            ],

            testing_strategy=analysis[
                "testing_strategy"
            ]

        )

        print("Issue analyzed.")

        print("\nRetrieving Relevant Code...\n")

        retrieved_chunks = retrieve_relevant_chunks(

            issue_data.title + "\n" + issue_data.body,

            top_k=5

        )

        print(
            f"Retrieved {len(retrieved_chunks)} code chunks."
        )

        print("\nGenerating Fix...\n")

        fix = self.fix_generator.generate_fix(

            issue_data,

            analysis,

            retrieved_chunks

        )

        print("Fix generated.")

        generated_files = {}

        for patch in fix.patches:

            generated_files[
                patch.path
            ] = patch.new_code

        print("\nRunning Validation...\n")

        report = self.validator.validate(

            repo_path,

            generated_files

        )

        validation = ValidationResult(

            passed=report["passed"],

            stdout=report["stdout"],

            stderr=report["stderr"]

        )

        print("Validation complete.")

        print("\nGenerating Pull Request...\n")

        pr = self.pr_generator.generate_pr(

            issue_data,

            analysis,

            fix,

            validation

        )

        return {

            "issue": issue_data,

            "analysis": analysis,

            "fix": fix,

            "validation": validation,

            "pull_request": pr

        }


if __name__ == "__main__":

    agent = OpenSourceFixAgent()

    result = agent.run(

        repo_url="https://github.com/pallets/flask",

        issue_number=1,

        repo_path="../repos/flask"

    )

    print("\n===========================")

    print(result["pull_request"].title)

    print("===========================\n")

    print(result["pull_request"].description)
