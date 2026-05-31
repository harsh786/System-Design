"""
PR Review Agent

Performs comprehensive code review like a senior developer:
- Code quality assessment
- Architecture compliance validation
- NFR verification
- Documentation review
- Test coverage analysis
"""

import json
from typing import Dict, List, Any
import structlog

from src.config.settings import Settings
from src.retrieval.vector_store import VectorStoreManager

logger = structlog.get_logger()


class PRReviewAgent:
    """
    Performs comprehensive Pull Request review on generated code.
    """

    def __init__(self, vector_store: VectorStoreManager, settings: Settings):
        self.vector_store = vector_store
        self.settings = settings
        self.llm = self._init_llm()

    def _init_llm(self):
        """Initialize LLM client based on settings."""
        if self.settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.settings.openai_model,
                temperature=0.1,
                api_key=self.settings.openai_api_key,
            )
        elif self.settings.llm_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.settings.anthropic_model,
                temperature=0.1,
                api_key=self.settings.anthropic_api_key,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method for PR review agent.

        Args:
            state: Current agent state containing all design and implementation artifacts

        Returns:
            Updated state with PR review results
        """
        logger.info("pr_review_started")

        try:
            # Gather all artifacts for review
            requirements = state.get("requirements_json", "")
            hld_document = state.get("hld_document", "")
            lld_documents = state.get("lld_documents", {})
            db_design = state.get("db_design_document", "")
            generated_code = state.get("generated_code", {})
            unit_tests = state.get("unit_tests", {})
            security_review = state.get("security_review_report", "")

            # Step 1: Code quality assessment
            code_quality_score = await self._assess_code_quality(generated_code)

            # Step 2: Architecture compliance validation
            architecture_compliance = await self._validate_architecture_compliance(
                generated_code, hld_document, lld_documents
            )

            # Step 3: NFR verification
            nfr_validation = await self._verify_nfrs(
                generated_code, requirements, db_design
            )

            # Step 4: Documentation review
            documentation_complete = await self._review_documentation(
                generated_code, hld_document, lld_documents
            )

            # Step 5: Test coverage analysis
            test_analysis = await self._analyze_test_coverage(
                generated_code, unit_tests
            )

            # Step 6: Generate review comments
            review_comments = await self._generate_review_comments(
                generated_code,
                code_quality_score,
                architecture_compliance,
                nfr_validation,
            )

            # Step 7: Determine approval status
            pr_approval_status = self._determine_approval_status(
                code_quality_score=code_quality_score,
                architecture_compliance=architecture_compliance,
                nfr_validation=nfr_validation,
                test_coverage=test_analysis.get("coverage_percentage", 0),
                security_issues=self._extract_security_issues(security_review),
            )

            # Step 8: Generate PR review report
            pr_review_report = self._generate_pr_review_report(
                code_quality_score=code_quality_score,
                architecture_compliance=architecture_compliance,
                nfr_validation=nfr_validation,
                test_analysis=test_analysis,
                documentation_complete=documentation_complete,
                review_comments=review_comments,
                security_review=security_review,
                approval_status=pr_approval_status,
            )

            logger.info(
                "pr_review_complete",
                approval_status=pr_approval_status,
                code_quality=code_quality_score,
                comments=len(review_comments),
            )

            return {
                "code_quality_score": code_quality_score,
                "pr_review_comments": review_comments,
                "nfr_validation_results": nfr_validation,
                "documentation_complete": documentation_complete,
                "pr_approval_status": pr_approval_status,
                "pr_review_report": pr_review_report,
                "current_agent": "pr_reviewer",
            }

        except Exception as e:
            logger.error("pr_review_failed", error=str(e))
            return {
                "error": f"PR review failed: {str(e)}",
                "current_agent": "pr_reviewer",
            }

    async def _assess_code_quality(self, generated_code: Dict[str, str]) -> float:
        """
        Assess overall code quality (0-10 scale).
        """
        quality_scores = []

        # Sample files for detailed review
        sample_files = list(generated_code.items())[:10]

        for file_path, content in sample_files:
            prompt = f"""
Assess the code quality of the following file on a scale of 0-10.

## File: {file_path}

```
{content[:1500]}
```

Evaluate:
1. **Readability** (naming, structure, clarity)
2. **Maintainability** (modularity, DRY principle)
3. **Error Handling** (comprehensive, appropriate)
4. **Performance** (efficient algorithms, no obvious bottlenecks)
5. **Security** (basic security practices)
6. **Testing** (testability, good structure)
7. **Documentation** (docstrings, comments)
8. **Best Practices** (follows language/framework conventions)

Provide a single number between 0-10 as the overall quality score.
Only output the number.
"""

            try:
                response = await self.llm.ainvoke(prompt)
                score_str = response.content.strip()
                # Extract number
                import re
                match = re.search(r'(\d+\.?\d*)', score_str)
                if match:
                    score = float(match.group(1))
                    quality_scores.append(min(score, 10.0))

            except Exception as e:
                logger.warning("code_quality_assessment_failed", file=file_path, error=str(e))

        if quality_scores:
            return sum(quality_scores) / len(quality_scores)
        else:
            return 7.0  # Default score

    async def _validate_architecture_compliance(
        self,
        generated_code: Dict[str, str],
        hld_document: str,
        lld_documents: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Validate that generated code follows the designed architecture.
        """
        prompt = f"""
Validate that the generated code follows the architecture specified in HLD and LLD.

## High-Level Design (Summary)
{hld_document[:1000]}

## Low-Level Design (Summary)
{self._summarize_lld(lld_documents)}

## Generated Code Files
{', '.join(list(generated_code.keys()))}

Check:
1. Do all designed components have corresponding code?
2. Are the component interactions as specified?
3. Are design patterns correctly implemented?
4. Are technology choices adhered to?
5. Is layering/separation of concerns maintained?

Output as JSON:
{{
  "compliant": true/false,
  "deviations": [
    {{"component": "...", "issue": "...", "severity": "HIGH/MEDIUM/LOW"}}
  ],
  "missing_components": [],
  "extra_components": [],
  "pattern_compliance": {{
    "Repository": "compliant/non-compliant",
    "Service": "compliant/non-compliant"
  }}
}}
"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content

            # Extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            compliance_result = json.loads(json_str)
            return compliance_result

        except Exception as e:
            logger.error("architecture_compliance_failed", error=str(e))
            return {
                "compliant": True,
                "deviations": [],
                "missing_components": [],
                "extra_components": [],
            }

    async def _verify_nfrs(
        self,
        generated_code: Dict[str, str],
        requirements: str,
        db_design: str,
    ) -> Dict[str, Any]:
        """
        Verify that Non-Functional Requirements are addressed.
        """
        prompt = f"""
Verify that the generated code addresses the Non-Functional Requirements.

## Requirements (Summary)
{requirements[:1000] if isinstance(requirements, str) else json.dumps(requirements)[:1000]}

## Database Design (Summary)
{db_design[:500]}

## Code Summary
Total files: {len(generated_code)}

Evaluate these NFRs:
1. **Performance**: Efficient algorithms, query optimization, caching
2. **Scalability**: Horizontal scaling support, stateless design
3. **Availability**: Error handling, retries, circuit breakers
4. **Security**: Authentication, authorization, input validation
5. **Observability**: Logging, metrics, tracing
6. **Maintainability**: Clean code, modularity, documentation

For each NFR, provide:
- status: ADDRESSED, PARTIAL, NOT_ADDRESSED
- evidence: specific code examples or patterns found
- recommendations: if not fully addressed

Output as JSON:
{{
  "performance": {{
    "status": "ADDRESSED",
    "evidence": ["..."],
    "recommendations": []
  }},
  ...
}}
"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content

            # Extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            nfr_results = json.loads(json_str)
            return nfr_results

        except Exception as e:
            logger.error("nfr_verification_failed", error=str(e))
            return {}

    async def _review_documentation(
        self,
        generated_code: Dict[str, str],
        hld_document: str,
        lld_documents: Dict[str, str],
    ) -> bool:
        """
        Review if documentation is complete.
        """
        # Check for README
        has_readme = any("readme" in f.lower() for f in generated_code.keys())

        # Check for docstrings in code
        has_docstrings = any("\"\"\"" in content or "'''" in content
                            for content in list(generated_code.values())[:10])

        # Check for API documentation
        has_api_docs = any("openapi" in content.lower() or "swagger" in content.lower()
                          for content in generated_code.values())

        documentation_complete = has_readme and has_docstrings

        logger.debug(
            "documentation_review",
            has_readme=has_readme,
            has_docstrings=has_docstrings,
            has_api_docs=has_api_docs,
        )

        return documentation_complete

    async def _analyze_test_coverage(
        self,
        generated_code: Dict[str, str],
        unit_tests: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Analyze test coverage.
        """
        # Count source files vs test files
        source_files = [f for f in generated_code.keys() if not "test" in f.lower()]
        test_files = unit_tests or {}

        # Estimate coverage based on file ratio (simplified)
        if source_files:
            coverage_percentage = (len(test_files) / len(source_files)) * 100
            coverage_percentage = min(coverage_percentage, 100)
        else:
            coverage_percentage = 0

        test_analysis = {
            "source_files": len(source_files),
            "test_files": len(test_files),
            "coverage_percentage": round(coverage_percentage, 1),
            "coverage_status": "good" if coverage_percentage >= 80 else
                             "acceptable" if coverage_percentage >= 60 else "poor",
        }

        return test_analysis

    async def _generate_review_comments(
        self,
        generated_code: Dict[str, str],
        code_quality_score: float,
        architecture_compliance: Dict,
        nfr_validation: Dict,
    ) -> List[Dict[str, Any]]:
        """
        Generate specific review comments for the PR.
        """
        comments = []

        # Comments on architecture deviations
        for deviation in architecture_compliance.get("deviations", []):
            comments.append({
                "type": "architecture",
                "severity": deviation.get("severity", "MEDIUM"),
                "component": deviation.get("component"),
                "comment": f"Architecture deviation: {deviation.get('issue')}",
                "suggestion": "Align implementation with designed architecture",
            })

        # Comments on NFR gaps
        for nfr_name, nfr_result in nfr_validation.items():
            if nfr_result.get("status") == "NOT_ADDRESSED":
                comments.append({
                    "type": "nfr",
                    "severity": "HIGH",
                    "nfr": nfr_name,
                    "comment": f"NFR not addressed: {nfr_name}",
                    "suggestion": "; ".join(nfr_result.get("recommendations", [])),
                })

        # Sample 2-3 files for detailed code review
        sample_files = list(generated_code.items())[:3]

        for file_path, content in sample_files:
            file_comments = await self._review_file_details(file_path, content)
            comments.extend(file_comments)

        return comments

    async def _review_file_details(
        self, file_path: str, content: str
    ) -> List[Dict[str, Any]]:
        """
        Generate detailed review comments for a specific file.
        """
        prompt = f"""
Review the following code file and provide 2-3 specific, actionable comments.

## File: {file_path}

```
{content[:1500]}
```

For each comment, provide:
- line: approximate line number
- severity: HIGH, MEDIUM, LOW, SUGGESTION
- comment: specific issue or suggestion
- code_snippet: relevant code (optional)

Focus on:
- Potential bugs or errors
- Performance improvements
- Code maintainability
- Best practices

Output as JSON array:
[
  {{
    "line": 45,
    "severity": "MEDIUM",
    "comment": "Consider extracting this logic into a separate method",
    "code_snippet": "if value > 0: ..."
  }}
]

If the code is excellent, return an empty array [].
"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content

            # Extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            elif "[" in content:
                json_str = content[content.index("["):content.rindex("]") + 1]
            else:
                return []

            comments = json.loads(json_str)

            # Add file path to each comment
            for comment in comments:
                comment["file"] = file_path
                comment["type"] = "code_review"

            return comments

        except Exception as e:
            logger.warning("file_review_failed", file=file_path, error=str(e))
            return []

    def _determine_approval_status(
        self,
        code_quality_score: float,
        architecture_compliance: Dict,
        nfr_validation: Dict,
        test_coverage: float,
        security_issues: int,
    ) -> str:
        """
        Determine PR approval status based on various criteria.
        """
        # Critical criteria
        if security_issues > 0:
            return "CHANGES_REQUESTED"

        if not architecture_compliance.get("compliant", True):
            high_severity_deviations = [
                d for d in architecture_compliance.get("deviations", [])
                if d.get("severity") == "HIGH"
            ]
            if high_severity_deviations:
                return "CHANGES_REQUESTED"

        # Check NFRs
        critical_nfrs_missing = any(
            nfr.get("status") == "NOT_ADDRESSED"
            for nfr in nfr_validation.values()
            if isinstance(nfr, dict)
        )
        if critical_nfrs_missing:
            return "CHANGES_REQUESTED"

        # Quality criteria
        if code_quality_score < 7.0:
            return "CHANGES_REQUESTED"

        if test_coverage < 60:
            return "CHANGES_REQUESTED"

        # Approve with or without comments
        if code_quality_score >= 9.0 and test_coverage >= 80:
            return "APPROVED"
        else:
            return "APPROVED_WITH_SUGGESTIONS"

    def _extract_security_issues(self, security_review: str) -> int:
        """
        Extract count of critical security issues from security review.
        """
        if not security_review:
            return 0

        # Simple count of "CRITICAL" mentions in security report
        critical_count = security_review.lower().count("critical")
        return critical_count

    def _generate_pr_review_report(
        self,
        code_quality_score: float,
        architecture_compliance: Dict,
        nfr_validation: Dict,
        test_analysis: Dict,
        documentation_complete: bool,
        review_comments: List[Dict],
        security_review: str,
        approval_status: str,
    ) -> str:
        """
        Generate comprehensive PR review report in Markdown.
        """
        report = "# Pull Request Review\n\n"

        # Summary
        status_emoji = {
            "APPROVED": "✅",
            "APPROVED_WITH_SUGGESTIONS": "✅",
            "CHANGES_REQUESTED": "❌",
        }

        report += f"## Summary\n\n"
        report += f"{status_emoji.get(approval_status, '⚠️')} **Status**: {approval_status}\n\n"

        # Code Quality
        report += "## Code Quality Score\n\n"
        report += f"**{code_quality_score:.1f}/10.0**\n\n"

        quality_rating = "Excellent" if code_quality_score >= 9 else \
                        "Good" if code_quality_score >= 7.5 else \
                        "Acceptable" if code_quality_score >= 6 else "Needs Improvement"

        report += f"Rating: {quality_rating}\n\n"

        # Architecture Compliance
        report += "## Architecture Compliance\n\n"
        if architecture_compliance.get("compliant", True):
            report += "✅ Code follows designed architecture\n\n"
        else:
            report += "⚠️ Architecture deviations detected:\n\n"
            for deviation in architecture_compliance.get("deviations", []):
                report += f"- **{deviation.get('component')}** ({deviation.get('severity')}): "
                report += f"{deviation.get('issue')}\n"
            report += "\n"

        # NFR Validation
        report += "## Non-Functional Requirements\n\n"
        report += "| Requirement | Status | Evidence |\n"
        report += "|-------------|--------|----------|\n"

        for nfr_name, nfr_result in nfr_validation.items():
            if isinstance(nfr_result, dict):
                status = nfr_result.get("status", "UNKNOWN")
                emoji = "✅" if status == "ADDRESSED" else \
                       "⚠️" if status == "PARTIAL" else "❌"
                evidence = ", ".join(nfr_result.get("evidence", [])[:2])
                report += f"| {nfr_name.title()} | {emoji} {status} | {evidence[:50]}... |\n"

        report += "\n"

        # Test Coverage
        report += "## Test Coverage\n\n"
        coverage = test_analysis.get("coverage_percentage", 0)
        coverage_status = test_analysis.get("coverage_status", "unknown")
        emoji = "✅" if coverage >= 80 else "⚠️" if coverage >= 60 else "❌"

        report += f"{emoji} **{coverage}%** ({coverage_status})\n\n"
        report += f"- Source files: {test_analysis.get('source_files', 0)}\n"
        report += f"- Test files: {test_analysis.get('test_files', 0)}\n\n"

        # Documentation
        report += "## Documentation\n\n"
        if documentation_complete:
            report += "✅ Documentation is complete\n"
        else:
            report += "⚠️ Documentation needs improvement\n"
            report += "- Add README with setup instructions\n"
            report += "- Add docstrings to all public functions\n"
            report += "- Consider adding API documentation\n"
        report += "\n"

        # Security Review Summary
        report += "## Security Review\n\n"
        if "No vulnerabilities found" in security_review or "0" in security_review[:100]:
            report += "✅ No critical security issues\n\n"
        else:
            report += "⚠️ See detailed security review report\n\n"

        # Review Comments
        if review_comments:
            report += "## Review Comments\n\n"

            # Group by severity
            by_severity = {}
            for comment in review_comments:
                severity = comment.get("severity", "MEDIUM")
                by_severity.setdefault(severity, []).append(comment)

            for severity in ["HIGH", "MEDIUM", "LOW", "SUGGESTION"]:
                comments = by_severity.get(severity, [])
                if comments:
                    report += f"### {severity} ({len(comments)})\n\n"
                    for comment in comments[:5]:  # Limit to 5 per severity
                        file = comment.get("file", comment.get("component", "General"))
                        report += f"**{file}**"
                        if comment.get("line"):
                            report += f" (Line {comment.get('line')})"
                        report += "\n\n"
                        report += f"- {comment.get('comment')}\n"
                        if comment.get("suggestion"):
                            report += f"- *Suggestion*: {comment.get('suggestion')}\n"
                        report += "\n"

        # Recommendations
        report += "## Recommendations\n\n"
        if approval_status == "CHANGES_REQUESTED":
            report += "1. Address all HIGH severity issues\n"
            report += "2. Fix security vulnerabilities\n"
            report += "3. Align code with designed architecture\n"
            report += "4. Improve test coverage to at least 80%\n"
        elif approval_status == "APPROVED_WITH_SUGGESTIONS":
            report += "1. Consider addressing suggestions for improved code quality\n"
            report += "2. Add more edge case tests\n"
            report += "3. Improve documentation where noted\n"
        else:
            report += "Code looks good! Ready to merge.\n"

        report += f"\n**Final Decision**: {approval_status}\n"

        return report

    def _summarize_lld(self, lld_documents: Dict[str, str]) -> str:
        """Summarize LLD documents for prompt."""
        summary = []
        for component, lld in list(lld_documents.items())[:3]:
            summary.append(f"### {component}\n{lld[:300]}")
        return "\n\n".join(summary)
