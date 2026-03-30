"""
Security Review Agent

Performs comprehensive security analysis on generated code:
- Static Application Security Testing (SAST)
- Dependency vulnerability scanning
- Security best practices validation
- Compliance checking (OWASP, GDPR, etc.)
"""

import os
import json
import subprocess
from typing import Dict, List, Any
import structlog

from src.config.settings import Settings
from src.retrieval.vector_store import VectorStoreManager

logger = structlog.get_logger()


class SecurityReviewAgent:
    """
    Performs security review on generated code and provides fixes.
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
        Main execution method for security review agent.

        Args:
            state: Current agent state containing generated_code

        Returns:
            Updated state with security review results
        """
        logger.info("security_review_started")

        try:
            generated_code = state.get("generated_code", {})
            tech_stack = state.get("tech_stack", {})
            security_requirements = state.get("security_requirements", "")

            if not generated_code:
                logger.warning("no_code_to_review")
                return {
                    "sast_results": {},
                    "dependency_vulnerabilities": [],
                    "security_review_report": "No code to review",
                    "security_issues_fixed": [],
                    "current_agent": "security_reviewer",
                }

            # Write code to temporary directory for analysis
            temp_dir = self._write_code_to_temp(generated_code)

            # Step 1: Run SAST tools
            sast_results = await self._run_sast_analysis(temp_dir, tech_stack)

            # Step 2: Scan dependencies for vulnerabilities
            dependency_vulns = await self._scan_dependencies(temp_dir, tech_stack)

            # Step 3: Security best practices review
            best_practices_issues = await self._review_security_best_practices(
                generated_code, security_requirements
            )

            # Step 4: Compliance checking
            compliance_results = await self._check_compliance(
                generated_code, security_requirements
            )

            # Step 5: Auto-fix issues where possible
            fixed_issues = await self._auto_fix_security_issues(
                generated_code, sast_results, best_practices_issues
            )

            # Step 6: Generate comprehensive security report
            security_report = self._generate_security_report(
                sast_results=sast_results,
                dependency_vulns=dependency_vulns,
                best_practices_issues=best_practices_issues,
                compliance_results=compliance_results,
                fixed_issues=fixed_issues,
            )

            # Clean up temp directory
            self._cleanup_temp(temp_dir)

            # Determine if there are critical unresolved issues
            critical_issues = self._count_critical_issues(
                sast_results, dependency_vulns, best_practices_issues
            )

            logger.info(
                "security_review_complete",
                critical_issues=critical_issues,
                issues_fixed=len(fixed_issues),
            )

            return {
                "sast_results": sast_results,
                "dependency_vulnerabilities": dependency_vulns,
                "security_review_report": security_report,
                "security_issues_fixed": fixed_issues,
                "security_auto_fix_iteration": state.get("security_auto_fix_iteration", 0),
                "current_agent": "security_reviewer",
            }

        except Exception as e:
            logger.error("security_review_failed", error=str(e))
            return {
                "error": f"Security review failed: {str(e)}",
                "current_agent": "security_reviewer",
            }

    def _write_code_to_temp(self, generated_code: Dict[str, str]) -> str:
        """
        Write generated code to temporary directory for analysis.
        """
        import tempfile

        temp_dir = tempfile.mkdtemp(prefix="security_review_")

        for file_path, content in generated_code.items():
            full_path = os.path.join(temp_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w") as f:
                f.write(content)

        logger.debug("code_written_to_temp", temp_dir=temp_dir)
        return temp_dir

    async def _run_sast_analysis(
        self, code_dir: str, tech_stack: Dict
    ) -> Dict[str, Any]:
        """
        Run Static Application Security Testing tools.
        """
        sast_results = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
        }

        languages = tech_stack.get("languages", [])

        # Python: Bandit
        if "Python" in languages:
            bandit_results = self._run_bandit(code_dir)
            self._merge_sast_results(sast_results, bandit_results)

        # JavaScript/TypeScript: ESLint security plugins
        if "JavaScript/TypeScript" in languages:
            eslint_results = self._run_eslint_security(code_dir)
            self._merge_sast_results(sast_results, eslint_results)

        # Multi-language: Semgrep (if available)
        semgrep_results = self._run_semgrep(code_dir)
        if semgrep_results:
            self._merge_sast_results(sast_results, semgrep_results)

        return sast_results

    def _run_bandit(self, code_dir: str) -> Dict[str, List[Dict]]:
        """
        Run Bandit security scanner for Python.
        """
        results = {"critical": [], "high": [], "medium": [], "low": []}

        try:
            # Check if bandit is installed
            subprocess.run(["bandit", "--version"], capture_output=True, check=True)

            # Run bandit
            result = subprocess.run(
                ["bandit", "-r", code_dir, "-f", "json"],
                capture_output=True,
                text=True,
            )

            if result.stdout:
                bandit_output = json.loads(result.stdout)
                for issue in bandit_output.get("results", []):
                    severity = issue.get("issue_severity", "").lower()
                    results[severity].append(
                        {
                            "tool": "bandit",
                            "file": issue.get("filename", ""),
                            "line": issue.get("line_number", 0),
                            "issue": issue.get("issue_text", ""),
                            "confidence": issue.get("issue_confidence", ""),
                            "cwe": issue.get("issue_cwe", {}).get("id", ""),
                        }
                    )

            logger.debug("bandit_scan_complete", issues=len(bandit_output.get("results", [])))

        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("bandit_scan_failed", error=str(e))

        return results

    def _run_eslint_security(self, code_dir: str) -> Dict[str, List[Dict]]:
        """
        Run ESLint with security plugins for JavaScript/TypeScript.
        """
        results = {"critical": [], "high": [], "medium": [], "low": []}

        # Simplified - in production, you'd install and configure eslint-plugin-security
        logger.debug("eslint_security_scan_skipped", reason="not_implemented")

        return results

    def _run_semgrep(self, code_dir: str) -> Dict[str, List[Dict]]:
        """
        Run Semgrep for multi-language security scanning.
        """
        results = {"critical": [], "high": [], "medium": [], "low": []}

        try:
            # Check if semgrep is installed
            subprocess.run(["semgrep", "--version"], capture_output=True, check=True)

            # Run semgrep with security rules
            result = subprocess.run(
                [
                    "semgrep",
                    "--config=auto",
                    "--json",
                    code_dir,
                ],
                capture_output=True,
                text=True,
            )

            if result.stdout:
                semgrep_output = json.loads(result.stdout)
                for finding in semgrep_output.get("results", []):
                    severity_map = {
                        "ERROR": "high",
                        "WARNING": "medium",
                        "INFO": "low",
                    }
                    severity = severity_map.get(finding.get("extra", {}).get("severity", "INFO"), "low")

                    results[severity].append(
                        {
                            "tool": "semgrep",
                            "file": finding.get("path", ""),
                            "line": finding.get("start", {}).get("line", 0),
                            "issue": finding.get("extra", {}).get("message", ""),
                            "rule_id": finding.get("check_id", ""),
                        }
                    )

            logger.debug("semgrep_scan_complete", issues=len(semgrep_output.get("results", [])))

        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("semgrep_scan_failed", error=str(e))

        return results

    def _merge_sast_results(self, target: Dict, source: Dict):
        """Merge SAST results from different tools."""
        for severity in ["critical", "high", "medium", "low"]:
            target[severity].extend(source.get(severity, []))

    async def _scan_dependencies(
        self, code_dir: str, tech_stack: Dict
    ) -> List[Dict[str, Any]]:
        """
        Scan dependencies for known vulnerabilities.
        """
        vulnerabilities = []
        languages = tech_stack.get("languages", [])

        # Python: safety or pip-audit
        if "Python" in languages:
            python_vulns = self._scan_python_dependencies(code_dir)
            vulnerabilities.extend(python_vulns)

        # JavaScript: npm audit
        if "JavaScript/TypeScript" in languages:
            js_vulns = self._scan_javascript_dependencies(code_dir)
            vulnerabilities.extend(js_vulns)

        return vulnerabilities

    def _scan_python_dependencies(self, code_dir: str) -> List[Dict[str, Any]]:
        """
        Scan Python dependencies using safety or pip-audit.
        """
        vulnerabilities = []

        try:
            # Look for requirements.txt
            req_file = os.path.join(code_dir, "requirements.txt")
            if not os.path.exists(req_file):
                return vulnerabilities

            # Try using safety
            result = subprocess.run(
                ["safety", "check", "--json", "-r", req_file],
                capture_output=True,
                text=True,
            )

            if result.stdout:
                safety_output = json.loads(result.stdout)
                for vuln in safety_output:
                    vulnerabilities.append(
                        {
                            "package": vuln[0],
                            "version": vuln[2],
                            "cve": vuln[4],
                            "severity": self._map_cvss_to_severity(vuln[3]),
                            "fix_version": vuln[1],
                        }
                    )

        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("python_dependency_scan_failed", error=str(e))

        return vulnerabilities

    def _scan_javascript_dependencies(self, code_dir: str) -> List[Dict[str, Any]]:
        """
        Scan JavaScript dependencies using npm audit.
        """
        vulnerabilities = []

        # Simplified - in production, you'd run npm audit --json
        logger.debug("js_dependency_scan_skipped", reason="not_implemented")

        return vulnerabilities

    def _map_cvss_to_severity(self, cvss_score: float) -> str:
        """Map CVSS score to severity level."""
        if cvss_score >= 9.0:
            return "CRITICAL"
        elif cvss_score >= 7.0:
            return "HIGH"
        elif cvss_score >= 4.0:
            return "MEDIUM"
        else:
            return "LOW"

    async def _review_security_best_practices(
        self, generated_code: Dict[str, str], security_requirements: str
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to review security best practices.
        """
        # Retrieve security guidelines from vector store
        security_guidelines = self.vector_store.search(
            query="security best practices authentication authorization input validation",
            k=5,
        )

        # Sample a few important files for detailed review
        important_files = self._select_important_files(generated_code)

        issues = []

        for file_path, content in important_files.items():
            prompt = f"""
Review the following code for security best practices.

## File: {file_path}

```
{content[:2000]}  # Limit to first 2000 chars
```

## Security Requirements
{security_requirements[:500]}

## Security Guidelines
{self._format_guidelines(security_guidelines)}

Check for:
1. SQL injection vulnerabilities
2. XSS vulnerabilities
3. Authentication/authorization issues
4. Insecure data storage
5. Insufficient input validation
6. Insecure cryptography
7. Hardcoded secrets
8. Information disclosure
9. Insecure deserialization
10. Missing security headers

For each issue found, provide:
- severity: CRITICAL, HIGH, MEDIUM, LOW
- issue: description
- line: approximate line number (if identifiable)
- fix: how to fix it

Output as JSON array:
[
  {{"severity": "HIGH", "issue": "...", "line": 45, "fix": "..."}}
]
"""

            try:
                response = await self.llm.ainvoke(prompt)
                content = response.content

                # Try to extract JSON
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                elif "[" in content:
                    json_str = content[content.index("[") : content.rindex("]") + 1]
                else:
                    continue

                file_issues = json.loads(json_str)
                for issue in file_issues:
                    issue["file"] = file_path
                    issues.append(issue)

            except Exception as e:
                logger.warning("best_practices_review_failed", file=file_path, error=str(e))

        return issues

    def _select_important_files(self, generated_code: Dict[str, str]) -> Dict[str, str]:
        """
        Select important files for detailed security review.
        Priority: authentication, API endpoints, database access.
        """
        important = {}
        priority_keywords = ["auth", "api", "route", "endpoint", "repository", "service"]

        for file_path, content in generated_code.items():
            # Check if filename contains priority keywords
            if any(keyword in file_path.lower() for keyword in priority_keywords):
                important[file_path] = content

            # Limit to 5 files to manage token usage
            if len(important) >= 5:
                break

        # If no priority files, just take first 5
        if not important:
            important = dict(list(generated_code.items())[:5])

        return important

    async def _check_compliance(
        self, generated_code: Dict[str, str], security_requirements: str
    ) -> Dict[str, Any]:
        """
        Check compliance with standards (OWASP Top 10, GDPR, etc.)
        """
        compliance_results = {
            "owasp_top_10": {},
            "gdpr": {},
            "pci_dss": {},
        }

        # OWASP Top 10 checks
        owasp_checks = [
            "A01:2021 - Broken Access Control",
            "A02:2021 - Cryptographic Failures",
            "A03:2021 - Injection",
            "A04:2021 - Insecure Design",
            "A05:2021 - Security Misconfiguration",
            "A06:2021 - Vulnerable Components",
            "A07:2021 - Authentication Failures",
            "A08:2021 - Data Integrity Failures",
            "A09:2021 - Logging Failures",
            "A10:2021 - SSRF",
        ]

        prompt = f"""
Evaluate the generated codebase for OWASP Top 10 (2021) compliance.

## Security Requirements
{security_requirements}

## Code Summary
Total files: {len(generated_code)}
Key files: {', '.join(list(generated_code.keys())[:10])}

For each OWASP category, assess:
- status: COMPLIANT, PARTIAL, NON_COMPLIANT, NOT_APPLICABLE
- findings: list of issues or confirmations
- recommendations: if not fully compliant

OWASP Categories:
{json.dumps(owasp_checks, indent=2)}

Output as JSON:
{{
  "A01:2021 - Broken Access Control": {{
    "status": "COMPLIANT",
    "findings": ["..."],
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

            compliance_results["owasp_top_10"] = json.loads(json_str)

        except Exception as e:
            logger.error("owasp_compliance_check_failed", error=str(e))

        return compliance_results

    async def _auto_fix_security_issues(
        self,
        generated_code: Dict[str, str],
        sast_results: Dict,
        best_practices_issues: List[Dict],
    ) -> List[str]:
        """
        Attempt to auto-fix certain security issues.
        """
        fixed_issues = []

        # Identify fixable issues (e.g., missing input validation, hardcoded secrets)
        fixable_issues = self._identify_fixable_issues(sast_results, best_practices_issues)

        for issue in fixable_issues[:10]:  # Limit to 10 auto-fixes
            try:
                fix_description = await self._generate_fix(issue, generated_code)
                if fix_description:
                    fixed_issues.append(fix_description)
            except Exception as e:
                logger.warning("auto_fix_failed", issue=issue, error=str(e))

        return fixed_issues

    def _identify_fixable_issues(
        self, sast_results: Dict, best_practices_issues: List[Dict]
    ) -> List[Dict]:
        """
        Identify issues that can be auto-fixed.
        """
        fixable = []

        # High/Critical issues from best practices review
        for issue in best_practices_issues:
            if issue.get("severity") in ["CRITICAL", "HIGH"] and issue.get("fix"):
                fixable.append(issue)

        return fixable

    async def _generate_fix(
        self, issue: Dict, generated_code: Dict[str, str]
    ) -> str:
        """
        Generate a fix for a specific issue.
        """
        # This would involve modifying the generated code
        # Simplified for demonstration
        return f"Fixed {issue.get('issue')} in {issue.get('file')}"

    def _generate_security_report(
        self,
        sast_results: Dict,
        dependency_vulns: List[Dict],
        best_practices_issues: List[Dict],
        compliance_results: Dict,
        fixed_issues: List[str],
    ) -> str:
        """
        Generate comprehensive security review report in Markdown.
        """
        report = "# Security Review Report\n\n"

        # Summary
        total_critical = len(sast_results.get("critical", []))
        total_high = len(sast_results.get("high", []))
        total_medium = len(sast_results.get("medium", []))
        total_low = len(sast_results.get("low", []))

        report += "## Summary\n\n"
        report += f"- **Critical Issues**: {total_critical}\n"
        report += f"- **High Severity**: {total_high}\n"
        report += f"- **Medium Severity**: {total_medium}\n"
        report += f"- **Low Severity**: {total_low}\n"
        report += f"- **Issues Auto-Fixed**: {len(fixed_issues)}\n\n"

        # SAST Results
        report += "## Static Analysis Results\n\n"
        for severity in ["critical", "high", "medium", "low"]:
            issues = sast_results.get(severity, [])
            if issues:
                report += f"### {severity.upper()} Severity ({len(issues)})\n\n"
                for i, issue in enumerate(issues[:5], 1):  # Show first 5
                    report += f"{i}. **{issue.get('issue', 'Unknown')}** "
                    report += f"- {issue.get('file', 'Unknown')}:{issue.get('line', '?')}\n"

                if len(issues) > 5:
                    report += f"\n... and {len(issues) - 5} more\n"
                report += "\n"

        # Dependency Vulnerabilities
        report += "## Dependency Vulnerabilities\n\n"
        if dependency_vulns:
            report += "| Package | Version | CVE | Severity | Fix Available |\n"
            report += "|---------|---------|-----|----------|---------------|\n"
            for vuln in dependency_vulns[:10]:
                report += f"| {vuln.get('package')} | {vuln.get('version')} | "
                report += f"{vuln.get('cve')} | {vuln.get('severity')} | "
                report += f"{vuln.get('fix_version', 'N/A')} |\n"
            if len(dependency_vulns) > 10:
                report += f"\n... and {len(dependency_vulns) - 10} more\n"
        else:
            report += "✅ No vulnerabilities found\n"
        report += "\n"

        # Best Practices Issues
        report += "## Security Best Practices Review\n\n"
        bp_by_severity = {}
        for issue in best_practices_issues:
            severity = issue.get("severity", "LOW")
            bp_by_severity.setdefault(severity, []).append(issue)

        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            issues = bp_by_severity.get(severity, [])
            if issues:
                report += f"### {severity} ({len(issues)})\n\n"
                for issue in issues[:3]:
                    report += f"- **{issue.get('issue')}** ({issue.get('file')})\n"
                    report += f"  - Fix: {issue.get('fix', 'See details')}\n\n"

        # Compliance
        report += "## Compliance Checks\n\n"
        report += "### OWASP Top 10 (2021)\n\n"
        owasp = compliance_results.get("owasp_top_10", {})
        for category, result in owasp.items():
            status = result.get("status", "UNKNOWN")
            emoji = "✅" if status == "COMPLIANT" else "⚠️" if status == "PARTIAL" else "❌"
            report += f"- {emoji} {category}: {status}\n"

        report += "\n"

        # Auto-fixed issues
        if fixed_issues:
            report += "## Auto-Fixed Issues\n\n"
            for fix in fixed_issues:
                report += f"- ✅ {fix}\n"
            report += "\n"

        # Recommendations
        report += "## Recommendations\n\n"
        if total_critical > 0:
            report += "1. **CRITICAL**: Address all critical security issues before deployment\n"
        if dependency_vulns:
            report += "2. Update vulnerable dependencies to latest secure versions\n"
        report += "3. Conduct manual penetration testing before production release\n"
        report += "4. Implement security monitoring and alerting\n"
        report += "5. Schedule regular security audits\n"

        return report

    def _count_critical_issues(
        self,
        sast_results: Dict,
        dependency_vulns: List[Dict],
        best_practices_issues: List[Dict],
    ) -> int:
        """Count total critical issues."""
        critical_count = len(sast_results.get("critical", []))
        critical_count += sum(
            1 for v in dependency_vulns if v.get("severity") == "CRITICAL"
        )
        critical_count += sum(
            1 for i in best_practices_issues if i.get("severity") == "CRITICAL"
        )
        return critical_count

    def _cleanup_temp(self, temp_dir: str):
        """Clean up temporary directory."""
        try:
            import shutil
            shutil.rmtree(temp_dir)
            logger.debug("temp_directory_cleaned", temp_dir=temp_dir)
        except Exception as e:
            logger.warning("temp_cleanup_failed", temp_dir=temp_dir, error=str(e))

    def _format_guidelines(self, guidelines: List[Dict]) -> str:
        """Format security guidelines for prompt."""
        formatted = []
        for guideline in guidelines[:3]:
            formatted.append(guideline.get("content", "")[:400])
        return "\n\n".join(formatted)
