# SonarQube & Code Quality - Complete Guide

## 1. Code Quality Fundamentals

### What is Code Quality?

Code quality refers to how well-written, maintainable, and reliable source code is. It encompasses multiple dimensions:

| Dimension | Description | Example |
|-----------|-------------|---------|
| **Reliability** | Code works correctly without bugs | Null pointer dereferences, resource leaks |
| **Security** | Code is free from vulnerabilities | SQL injection, XSS, hardcoded credentials |
| **Maintainability** | Code is easy to understand and modify | Clear naming, low complexity, no duplication |
| **Coverage** | Code is adequately tested | Unit tests cover critical paths |
| **Duplications** | Code avoids copy-paste | DRY principle violations |

### Technical Debt

Technical debt is the implied cost of future rework caused by choosing quick/easy solutions over better approaches.

```
Technical Debt Ratio = (Remediation Cost / Development Cost) × 100%

Example:
- Development cost: 100 person-days
- Remediation cost: 15 person-days
- Technical Debt Ratio: 15% (Rating: C)

Ratings:
  A: ≤ 5%
  B: 6-10%
  C: 11-20%
  D: 21-50%
  E: > 50%
```

**Cost of fixing vs cost of leaving:**
- Fix now: Low cost, simple change
- Fix later: Higher cost (forgotten context, cascading changes, regression risk)
- Never fix: Compounding interest - slows all future development

### Code Smells, Bugs, Vulnerabilities

| Type | Definition | Example |
|------|-----------|---------|
| **Bug** | Code that is demonstrably wrong | Null dereference, infinite loop, wrong operator |
| **Vulnerability** | Code open to attack | SQL injection, path traversal, weak crypto |
| **Code Smell** | Maintainability issue, not a bug | Long method, deep nesting, unused variable |
| **Security Hotspot** | Security-sensitive code needing review | Cookie settings, regex DoS, file permissions |

### Shift-Left Testing

Find issues as early as possible in the development lifecycle:

```
Cost of fixing a bug:
  IDE/Local:      $1x (cheapest)
  CI/Build:       $5x
  QA/Testing:     $10x
  Staging:        $50x
  Production:     $100x+ (most expensive)

Shift-left approach:
  Developer IDE → Pre-commit hooks → CI pipeline → Quality Gate → Deploy
       ↑                ↑                ↑              ↑
    SonarLint       lint/format       SonarQube     Pass/Fail
```

---

## 2. SonarQube Overview

### What is SonarQube?

SonarQube is an open-source platform for continuous inspection of code quality. It performs automatic reviews with static analysis to detect bugs, code smells, and security vulnerabilities in 30+ programming languages.

### Editions

| Edition | Use Case | Key Features |
|---------|----------|--------------|
| **Community** (Free) | Small teams, OSS | 15+ languages, basic analysis |
| **Developer** | Professional teams | Branch analysis, PR decoration, 27+ languages |
| **Enterprise** | Large organizations | Portfolio management, regulatory reports, OWASP/SANS |
| **Data Center** | High availability | Horizontal scaling, component redundancy |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SonarQube Server                          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Web Server  │  │   Compute    │  │  Search Server   │  │
│  │   (UI/API)   │  │   Engine     │  │  (Elasticsearch) │  │
│  │   Port 9000  │  │  (Analysis)  │  │    Port 9001     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │    PostgreSQL DB    │
                    │  (rules, metrics,  │
                    │   projects, users) │
                    └────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  SonarScanner    │────────▶│  SonarQube API   │
│  (runs on CI/    │  Report │  (receives and   │
│   developer box) │────────▶│   stores results)│
└──────────────────┘         └──────────────────┘
```

### Supported Languages

**Tier 1 (full support):** Java, JavaScript, TypeScript, C#, Python, Go, PHP, C/C++, Kotlin, Ruby, Scala, Swift, Objective-C

**Tier 2 (community/plugins):** Rust, Terraform (HCL), Dockerfile, YAML, XML, HTML, CSS, SQL, PL/SQL, T-SQL, ABAP, COBOL, Apex, VB.NET

---

## 3. SonarQube Concepts

### Quality Gates

A Quality Gate is a set of conditions that a project must meet before it can be considered production-ready.

**Default "Sonar way" Quality Gate conditions (on New Code):**

| Condition | Operator | Value |
|-----------|----------|-------|
| Coverage on New Code | is less than | 80% |
| Duplicated Lines on New Code | is greater than | 3% |
| Maintainability Rating on New Code | is worse than | A |
| Reliability Rating on New Code | is worse than | A |
| Security Hotspots Reviewed on New Code | is less than | 100% |
| Security Rating on New Code | is worse than | A |

**Custom Quality Gates example:**

```
# Strict gate for payment services
Payment Service Gate:
  - New Bugs = 0
  - New Vulnerabilities = 0
  - New Code Coverage ≥ 90%
  - New Duplications < 2%
  - Security Hotspots Reviewed = 100%
  - Cognitive Complexity per method < 15

# Relaxed gate for legacy migration
Legacy Migration Gate:
  - New Bugs = 0
  - New Vulnerabilities = 0
  - New Code Coverage ≥ 60%
  - New Duplications < 5%
```

### Quality Profiles

A Quality Profile is a collection of rules that apply to a specific language for a given project.

**Built-in profile: "Sonar way"**
- Curated set of ~300-500 rules per language
- Updated with each SonarQube version
- Balanced between strictness and noise

**Customization:**

```
Profile Hierarchy:
  Sonar way (built-in, read-only)
    └── Company Baseline (extends Sonar way)
          ├── Microservices Profile (adds API rules)
          ├── Frontend Profile (adds accessibility rules)
          └── Security Critical (adds extra security rules)

Actions:
  - Activate/deactivate individual rules
  - Change severity (Blocker → Major)
  - Set rule parameters (max method length = 30 lines)
  - Create rule inheritance chain
```

### Issues

**Types:**
- **Bug**: Something that is wrong and will lead to unexpected behavior
- **Vulnerability**: A point in code open to attack
- **Code Smell**: A maintainability issue that makes code harder to understand
- **Security Hotspot**: Security-sensitive code that needs manual review

**Severity levels:**

| Severity | Description | Example |
|----------|-------------|---------|
| **Blocker** | Bug with high probability to impact production | Memory leak in loop, data corruption |
| **Critical** | Bug with low probability to impact OR security flaw | Null deref in edge case, SQL injection |
| **Major** | Quality flaw that can highly impact productivity | Overly complex method, uncovered code |
| **Minor** | Quality flaw that can slightly impact productivity | Naming convention, unused import |
| **Info** | Not a quality flaw, just a finding | TODO comment, deprecated API usage |

**Issue Lifecycle:**

```
Open ──→ Confirmed ──→ Fixed ──→ Closed
  │          │
  │          └──→ Won't Fix (acceptable)
  │
  └──→ False Positive (incorrect detection)
  │
  └──→ Accepted (known, deferred)
```

### Metrics

**Reliability (Bugs):**
```
A = 0 bugs
B = at least 1 minor bug
C = at least 1 major bug
D = at least 1 critical bug
E = at least 1 blocker bug
```

**Security (Vulnerabilities):**
```
A = 0 vulnerabilities
B = at least 1 minor vulnerability
C = at least 1 major vulnerability
D = at least 1 critical vulnerability
E = at least 1 blocker vulnerability
```

**Maintainability (Technical Debt Ratio):**
```
A = ≤ 5% debt ratio
B = 6-10%
C = 11-20%
D = 21-50%
E = > 50%
```

**Coverage:**
```
Line Coverage = (lines executed by tests / total executable lines) × 100%
Branch Coverage = (branches executed / total branches) × 100%
Condition Coverage = (conditions evaluated to both true and false / total conditions) × 100%
```

**Complexity:**
```
Cyclomatic Complexity: Number of independent paths through code
  - Each if/for/while/case/catch/&&/|| adds 1
  - Lower is better (< 10 per method recommended)

Cognitive Complexity: How hard code is to understand
  - Increments for: nesting, breaks in flow, recursion
  - Penalizes deep nesting more heavily
  - Better reflects actual readability difficulty
```

### New Code Period (Clean as You Code)

The "New Code" period defines what code is considered "new" for quality gate evaluation:

```
Options:
  1. Previous Version: Since last version tag (recommended for releases)
  2. Number of Days: Last 30 days (for continuous delivery)
  3. Reference Branch: Compared to main/develop (for feature branches)
  4. Specific Date: Since a specific analysis date

Philosophy: "Clean as You Code"
  - Don't try to fix ALL existing issues
  - Ensure ALL new/changed code meets quality standards
  - Over time, overall quality naturally improves
  - Practical approach for legacy codebases
```

---

## 4. SonarQube Setup & Configuration

### Installation Methods

**Docker (recommended for evaluation):**

```yaml
# docker-compose.yml
version: "3"
services:
  sonarqube:
    image: sonarqube:lts-community
    container_name: sonarqube
    depends_on:
      - db
    ports:
      - "9000:9000"
    environment:
      SONAR_JDBC_URL: jdbc:postgresql://db:5432/sonar
      SONAR_JDBC_USERNAME: sonar
      SONAR_JDBC_PASSWORD: sonar
    volumes:
      - sonarqube_data:/opt/sonarqube/data
      - sonarqube_extensions:/opt/sonarqube/extensions
      - sonarqube_logs:/opt/sonarqube/logs
    ulimits:
      nofile:
        soft: 131072
        hard: 131072

  db:
    image: postgres:15
    container_name: sonarqube-db
    environment:
      POSTGRES_USER: sonar
      POSTGRES_PASSWORD: sonar
      POSTGRES_DB: sonar
    volumes:
      - postgresql_data:/var/lib/postgresql/data

volumes:
  sonarqube_data:
  sonarqube_extensions:
  sonarqube_logs:
  postgresql_data:
```

**Kubernetes (Helm):**

```bash
helm repo add sonarqube https://SonarSource.github.io/helm-chart-sonarqube
helm repo update

helm install sonarqube sonarqube/sonarqube \
  --namespace sonarqube \
  --create-namespace \
  --set persistence.enabled=true \
  --set postgresql.enabled=true \
  --set ingress.enabled=true \
  --set ingress.hosts[0].name=sonar.company.com
```

**System requirements:**
```
Minimum (small projects):
  - 2 vCPU, 4GB RAM, 30GB disk
  
Recommended (50+ projects):
  - 4 vCPU, 8GB RAM, 100GB SSD
  
Production (100+ projects):
  - 8 vCPU, 16GB RAM, 250GB SSD
  - Separate PostgreSQL server
  - vm.max_map_count = 524288 (for Elasticsearch)
  - fs.file-max = 131072
```

### Scanner Types

**SonarScanner CLI (generic - works for any language):**

```bash
# Install
brew install sonar-scanner  # macOS
# or download from https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/

# Run
sonar-scanner \
  -Dsonar.projectKey=my-project \
  -Dsonar.sources=src \
  -Dsonar.host.url=http://sonarqube:9000 \
  -Dsonar.token=sqp_xxxxxxxxxxxx
```

**SonarScanner for Maven:**

```xml
<!-- pom.xml -->
<properties>
  <sonar.projectKey>my-java-project</sonar.projectKey>
  <sonar.host.url>http://sonarqube:9000</sonar.host.url>
  <sonar.coverage.jacoco.xmlReportPaths>
    ${project.basedir}/target/site/jacoco/jacoco.xml
  </sonar.coverage.jacoco.xmlReportPaths>
</properties>

<!-- Run: mvn clean verify sonar:sonar -Dsonar.token=sqp_xxx -->
```

**SonarScanner for Gradle:**

```groovy
// build.gradle
plugins {
    id "org.sonarqube" version "4.4.1.3373"
}

sonar {
    properties {
        property "sonar.projectKey", "my-gradle-project"
        property "sonar.host.url", "http://sonarqube:9000"
        property "sonar.coverage.jacoco.xmlReportPaths",
                 "${buildDir}/reports/jacoco/test/jacocoTestReport.xml"
    }
}

// Run: ./gradlew sonar -Dsonar.token=sqp_xxx
```

**SonarScanner for .NET:**

```bash
# Install
dotnet tool install --global dotnet-sonarscanner

# Run (three-step process)
dotnet sonarscanner begin \
  /k:"my-dotnet-project" \
  /d:sonar.host.url="http://sonarqube:9000" \
  /d:sonar.token="sqp_xxx" \
  /d:sonar.cs.opencover.reportsPaths="**/coverage.opencover.xml"

dotnet build
dotnet test --collect:"XPlat Code Coverage"

dotnet sonarscanner end /d:sonar.token="sqp_xxx"
```

**SonarScanner for npm/Node.js:**

```json
// package.json
{
  "scripts": {
    "sonar": "sonar-scanner"
  },
  "devDependencies": {
    "sonarqube-scanner": "^3.3.0"
  }
}
```

### sonar-project.properties

```properties
# Project identification
sonar.projectKey=my-org_my-project
sonar.projectName=My Project
sonar.projectVersion=1.0.0

# Source configuration
sonar.sources=src
sonar.tests=test
sonar.sourceEncoding=UTF-8

# Language-specific
sonar.java.binaries=target/classes
sonar.java.libraries=target/dependency/*.jar

# Exclusions
sonar.exclusions=**/node_modules/**,**/vendor/**,**/*.generated.*,**/migrations/**
sonar.test.exclusions=**/test/**,**/*.test.*,**/*.spec.*
sonar.coverage.exclusions=**/config/**,**/dto/**,**/entity/**,**/*Config.java

# Coverage reports
sonar.javascript.lcov.reportPaths=coverage/lcov.info
sonar.python.coverage.reportPaths=coverage.xml
sonar.go.coverage.reportPaths=coverage.out
sonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml

# Duplications
sonar.cpd.exclusions=**/dto/**,**/entity/**

# Quality Gate
sonar.qualitygate.wait=true

# Branch (Developer Edition+)
# sonar.branch.name=feature/my-feature
```

### Authentication

```
Methods (in order of recommendation):
1. Project/Global Tokens (recommended)
   - Generate in: User > My Account > Security > Generate Token
   - Types: User Token, Project Analysis Token, Global Analysis Token
   - Use: SONAR_TOKEN environment variable

2. LDAP Integration
   - sonar.properties: sonar.security.realm=LDAP
   - Configure: sonar.ldap.url, sonar.ldap.bindDn, sonar.ldap.user.baseDn

3. SAML SSO
   - Configure in Administration > Authentication > SAML
   - Works with: Okta, Azure AD, OneLogin, Keycloak

4. GitHub/GitLab/Bitbucket OAuth
   - ALM integration for PR decoration
   - Developer Edition+ for full integration

5. HTTP Header Authentication (reverse proxy)
   - For enterprise SSO proxies
```

---

## 5. SonarQube with CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/sonar.yml
name: SonarQube Analysis

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  sonarqube:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for accurate blame/new code

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install & Test with Coverage
        run: |
          npm ci
          npm run test -- --coverage

      - name: SonarQube Scan
        uses: SonarSource/sonarqube-scan-action@master
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}

      - name: SonarQube Quality Gate
        uses: SonarSource/sonarqube-quality-gate-action@master
        timeout-minutes: 5
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

**Java project with Maven:**

```yaml
# .github/workflows/sonar-java.yml
name: SonarQube Java

on:
  push:
    branches: [main]
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: 17
          distribution: 'temurin'
          cache: 'maven'

      - name: Build and analyze
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
        run: |
          mvn -B verify sonar:sonar \
            -Dsonar.projectKey=my-java-project \
            -Dsonar.qualitygate.wait=true
```

### Jenkins

```groovy
// Jenkinsfile (Declarative Pipeline)
pipeline {
    agent any

    tools {
        maven 'Maven-3.9'
        jdk 'JDK-17'
    }

    environment {
        SONAR_SCANNER_HOME = tool 'SonarQubeScanner'
    }

    stages {
        stage('Build & Test') {
            steps {
                sh 'mvn clean verify'
            }
        }

        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('SonarQube-Server') {
                    sh """
                        mvn sonar:sonar \
                          -Dsonar.projectKey=jenkins-project \
                          -Dsonar.java.coveragePlugin=jacoco
                    """
                }
            }
        }

        stage('Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                sh './deploy.sh'
            }
        }
    }

    post {
        failure {
            slackSend channel: '#builds',
                      message: "Quality Gate FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
        }
    }
}
```

### Azure DevOps

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main
      - develop

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: SonarQubePrepare@5
    inputs:
      SonarQube: 'SonarQube-Connection'
      scannerMode: 'MSBuild'  # or 'CLI' for non-.NET
      projectKey: 'my-ado-project'
      extraProperties: |
        sonar.cs.opencover.reportsPaths=$(Build.SourcesDirectory)/**/coverage.opencover.xml

  - task: DotNetCoreCLI@2
    inputs:
      command: 'build'

  - task: DotNetCoreCLI@2
    inputs:
      command: 'test'
      arguments: '--collect:"XPlat Code Coverage" -- DataCollectionRunSettings.DataCollectors.DataCollector.Configuration.Format=opencover'

  - task: SonarQubeAnalyze@5

  - task: SonarQubePublish@5
    inputs:
      pollingTimeoutSec: '300'
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - test
  - quality

test:
  stage: test
  image: node:20
  script:
    - npm ci
    - npm run test:coverage
  artifacts:
    paths:
      - coverage/

sonarqube:
  stage: quality
  image:
    name: sonarsource/sonar-scanner-cli:latest
    entrypoint: [""]
  variables:
    SONAR_USER_HOME: "${CI_PROJECT_DIR}/.sonar"
    GIT_DEPTH: "0"
  cache:
    key: "${CI_JOB_NAME}"
    paths:
      - .sonar/cache
  script:
    - sonar-scanner
      -Dsonar.projectKey=${CI_PROJECT_NAME}
      -Dsonar.sources=src
      -Dsonar.host.url=${SONAR_HOST_URL}
      -Dsonar.token=${SONAR_TOKEN}
      -Dsonar.qualitygate.wait=true
      -Dsonar.javascript.lcov.reportPaths=coverage/lcov.info
  dependencies:
    - test
  only:
    - main
    - merge_requests
```

### Branch Analysis & PR Decoration

```
Branch Analysis (Developer Edition+):
  - Main branch: full analysis, historical data
  - Feature branches: compared against target branch
  - Short-lived branches: auto-deleted after merge

PR Decoration:
  - Inline comments on new issues in PR
  - Quality Gate status as PR check
  - Summary comment with metrics

  Configuration:
  1. Create ALM integration (GitHub/GitLab/Azure DevOps)
  2. Configure project binding
  3. Set up webhook for quality gate status
```

---

## 6. SonarCloud (SaaS)

### Overview

SonarCloud is the cloud-hosted version of SonarQube, managed by SonarSource.

| Feature | SonarQube | SonarCloud |
|---------|-----------|------------|
| Hosting | Self-managed | SaaS (sonarcloud.io) |
| Free tier | Community Edition | Free for public repos |
| Setup | Install & configure | Connect repo, done |
| Maintenance | You manage upgrades | Automatic |
| Branch analysis | Developer Edition+ | All plans |
| PR decoration | Developer Edition+ | All plans |
| Custom rules | Yes (plugins) | Limited |
| On-premise data | Yes | No (cloud only) |
| Languages | 30+ | 30+ |

### SonarCloud Setup

```yaml
# .github/workflows/sonarcloud.yml
name: SonarCloud
on:
  push:
    branches: [main]
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  sonarcloud:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: SonarCloud Scan
        uses: SonarSource/sonarcloud-github-action@master
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
        with:
          args: >
            -Dsonar.organization=my-org
            -Dsonar.projectKey=my-org_my-project
```

```properties
# sonar-project.properties (for SonarCloud)
sonar.organization=my-org
sonar.projectKey=my-org_my-project
sonar.sources=src
sonar.tests=test
sonar.javascript.lcov.reportPaths=coverage/lcov.info
```

---

## 7. Code Coverage Tools

### Java: JaCoCo

```xml
<!-- pom.xml -->
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.11</version>
    <executions>
        <execution>
            <id>prepare-agent</id>
            <goals><goal>prepare-agent</goal></goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>verify</phase>
            <goals><goal>report</goal></goals>
        </execution>
        <execution>
            <id>check</id>
            <goals><goal>check</goal></goals>
            <configuration>
                <rules>
                    <rule>
                        <element>BUNDLE</element>
                        <limits>
                            <limit>
                                <counter>LINE</counter>
                                <value>COVEREDRATIO</value>
                                <minimum>0.80</minimum>
                            </limit>
                        </limits>
                    </rule>
                </rules>
            </configuration>
        </execution>
    </executions>
</plugin>
```

### JavaScript/TypeScript: Jest + Istanbul

```json
// jest.config.js or package.json
{
  "jest": {
    "collectCoverage": true,
    "coverageDirectory": "coverage",
    "coverageReporters": ["lcov", "text", "text-summary"],
    "coverageThreshold": {
      "global": {
        "branches": 80,
        "functions": 80,
        "lines": 80,
        "statements": 80
      }
    },
    "collectCoverageFrom": [
      "src/**/*.{ts,tsx}",
      "!src/**/*.d.ts",
      "!src/**/index.ts"
    ]
  }
}
```

### Python: pytest-cov

```ini
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=src --cov-report=xml --cov-report=term --cov-fail-under=80"

[tool.coverage.run]
branch = true
source = ["src"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

```bash
# Run
pytest --cov=src --cov-report=xml:coverage.xml
# SonarQube property: sonar.python.coverage.reportPaths=coverage.xml
```

### Go: Built-in Coverage

```bash
# Generate coverage
go test ./... -coverprofile=coverage.out -covermode=atomic

# View HTML report
go tool cover -html=coverage.out -o coverage.html

# SonarQube property: sonar.go.coverage.reportPaths=coverage.out
```

### .NET: Coverlet

```bash
dotnet test --collect:"XPlat Code Coverage" \
  -- DataCollectionRunSettings.DataCollectors.DataCollector.Configuration.Format=opencover

# SonarQube property: sonar.cs.opencover.reportsPaths=**/coverage.opencover.xml
```

### Importing Coverage into SonarQube

```properties
# sonar-project.properties - Coverage report paths
# Java (JaCoCo XML)
sonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml

# JavaScript/TypeScript (LCOV)
sonar.javascript.lcov.reportPaths=coverage/lcov.info

# Python (Cobertura XML)
sonar.python.coverage.reportPaths=coverage.xml

# Go
sonar.go.coverage.reportPaths=coverage.out

# C# (OpenCover)
sonar.cs.opencover.reportsPaths=**/coverage.opencover.xml

# Generic (any language)
sonar.coverageReportPaths=coverage-report.xml
```

---

## 8. Other Code Quality Tools

### ESLint (JavaScript/TypeScript)

```javascript
// eslint.config.js (flat config - ESLint 9+)
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import prettier from 'eslint-config-prettier';

export default [
  js.configs.recommended,
  ...tseslint.configs.recommended,
  prettier,
  {
    rules: {
      'no-console': 'warn',
      '@typescript-eslint/no-unused-vars': 'error',
      '@typescript-eslint/explicit-function-return-type': 'warn',
      'complexity': ['error', 10],
      'max-depth': ['error', 3],
      'max-lines-per-function': ['warn', 50],
    },
  },
  {
    ignores: ['dist/', 'node_modules/', '*.config.js'],
  },
];
```

### Prettier (Formatting)

```json
// .prettierrc
{
  "semi": true,
  "trailingComma": "all",
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 2
}
```

### golangci-lint (Go)

```yaml
# .golangci.yml
run:
  timeout: 5m

linters:
  enable:
    - errcheck
    - gosimple
    - govet
    - ineffassign
    - staticcheck
    - unused
    - gocyclo
    - dupl
    - gosec
    - misspell
    - gocritic
    - revive

linters-settings:
  gocyclo:
    min-complexity: 10
  dupl:
    threshold: 100
  gosec:
    severity: medium

issues:
  exclude-rules:
    - path: _test\.go
      linters: [dupl, gosec]
```

### Semgrep (Lightweight SAST)

```yaml
# .semgrep.yml
rules:
  - id: no-hardcoded-secrets
    patterns:
      - pattern: |
          $KEY = "..."
      - metavariable-regex:
          metavariable: $KEY
          regex: (password|secret|token|api_key)
    message: "Hardcoded secret detected"
    severity: ERROR
    languages: [python, javascript, go, java]

  - id: sql-injection
    patterns:
      - pattern: |
          cursor.execute(f"... {$VAR} ...")
    message: "Possible SQL injection via f-string"
    severity: ERROR
    languages: [python]
```

```bash
# Run Semgrep
semgrep --config auto .                    # Auto-detect rules
semgrep --config p/owasp-top-ten .         # OWASP rules
semgrep --config .semgrep.yml .            # Custom rules
```

### CodeQL (GitHub Advanced Security)

```yaml
# .github/workflows/codeql.yml
name: CodeQL Analysis
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6am

jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    strategy:
      matrix:
        language: ['javascript', 'python']
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
          queries: security-extended
      - uses: github/codeql-action/autobuild@v3
      - uses: github/codeql-action/analyze@v3
```

### Python Tools

```ini
# pyproject.toml
[tool.pylint.messages_control]
disable = ["missing-docstring", "too-few-public-methods"]
max-line-length = 120

[tool.mypy]
strict = true
ignore_missing_imports = true

[tool.black]
line-length = 120
target-version = ['py311']

[tool.ruff]
line-length = 120
select = ["E", "F", "I", "N", "W", "UP", "S", "B", "A", "COM", "C4"]
ignore = ["E501"]
```

---

## 9. Security Analysis (SAST/DAST/SCA)

### SAST (Static Application Security Testing)

Analyzes source code without executing it.

| Tool | Type | Languages | Best For |
|------|------|-----------|----------|
| SonarQube | General + Security | 30+ | Combined quality + security |
| CodeQL | Deep semantic | 10+ | Complex vulnerability patterns |
| Semgrep | Pattern-based | 30+ | Custom rules, fast scans |
| Checkmarx | Enterprise | 25+ | Enterprise compliance |
| Fortify | Enterprise | 25+ | Government/defense |
| Snyk Code | Developer-first | 10+ | IDE + CI integration |

### DAST (Dynamic Application Security Testing)

Tests running applications for vulnerabilities.

```bash
# OWASP ZAP - Quick scan
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://myapp.staging.com \
  -r report.html

# OWASP ZAP - Full scan
docker run -t owasp/zap2docker-stable zap-full-scan.py \
  -t https://myapp.staging.com \
  -r full-report.html \
  -c zap-config.conf
```

### SCA (Software Composition Analysis)

Identifies vulnerabilities in third-party dependencies.

```yaml
# GitHub Dependabot (.github/dependabot.yml)
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"

  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

```bash
# Snyk
snyk test              # Test for vulnerabilities
snyk monitor           # Monitor for new vulnerabilities
snyk fix               # Auto-fix where possible

# OWASP Dependency-Check
dependency-check --project "MyApp" --scan ./src --format HTML

# Trivy (containers)
trivy image myapp:latest
trivy fs .                    # File system scan
trivy config .                # IaC misconfigurations
```

### OWASP Top 10 (2021)

| # | Category | Example | Detection |
|---|----------|---------|-----------|
| A01 | Broken Access Control | IDOR, privilege escalation | SAST + DAST |
| A02 | Cryptographic Failures | Weak encryption, plaintext secrets | SAST |
| A03 | Injection | SQL, NoSQL, OS command, LDAP | SAST + DAST |
| A04 | Insecure Design | Missing rate limiting, no threat model | Manual review |
| A05 | Security Misconfiguration | Default credentials, verbose errors | DAST + IaC scan |
| A06 | Vulnerable Components | Outdated libraries with CVEs | SCA |
| A07 | Auth Failures | Weak passwords, missing MFA | DAST |
| A08 | Data Integrity Failures | Insecure deserialization, no CI/CD verification | SAST |
| A09 | Logging Failures | Missing audit logs, log injection | SAST |
| A10 | SSRF | Internal service access via user input | SAST + DAST |

### Container & IaC Scanning

```bash
# Trivy - Container scanning
trivy image --severity HIGH,CRITICAL nginx:latest

# tfsec - Terraform scanning
tfsec ./terraform/

# Checkov - Multi-framework IaC
checkov -d ./terraform/
checkov -d ./cloudformation/
checkov --framework dockerfile -f Dockerfile

# GitLeaks - Secret scanning
gitleaks detect --source=. --report-path=gitleaks-report.json

# TruffleHog - Deep secret scanning
trufflehog git file://. --only-verified
```

### Complete Security Pipeline

```yaml
# .github/workflows/security.yml
name: Security Pipeline
on: [push, pull_request]

jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Semgrep SAST
        uses: semgrep/semgrep-action@v1
        with:
          config: p/owasp-top-ten p/r2c-security-audit

  sca:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Snyk SCA
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high

  container-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .
      - name: Trivy scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myapp:${{ github.sha }}
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: GitLeaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  dast:
    runs-on: ubuntu-latest
    needs: [sast, sca]  # Only after static checks pass
    steps:
      - name: ZAP Scan
        uses: zaproxy/action-baseline@v0.10.0
        with:
          target: 'https://staging.myapp.com'
```

---

## 10. Best Practices

### Clean as You Code

```
Strategy:
1. Set quality gate on NEW CODE only
2. Don't try to fix all legacy issues at once
3. Every new commit/PR must pass quality gate
4. Overall quality improves naturally over time

Implementation:
- New Code Period: "Previous Version" or "Reference Branch"
- Quality Gate: strict on new code, lenient on overall
- Track improvement trend over sprints
```

### Quality Gate as Deployment Gate

```
Pipeline flow:
  Build → Test → SonarQube → Quality Gate Check → Deploy
                                    │
                                    ├── PASS → Continue to deploy
                                    └── FAIL → Block deployment, notify team

Configuration:
  sonar.qualitygate.wait=true  (blocks until gate result)
  
  Jenkins: waitForQualityGate abortPipeline: true
  GitHub Actions: sonarqube-quality-gate-action
```

### Coverage Targets (Realistic)

```
Recommended targets:
  New code:     80% line coverage (strict)
  Overall:      60-70% (achievable for most projects)
  Critical:     90%+ (payment, auth, data processing)

What NOT to cover (exclude from metrics):
  - DTOs / POJOs / data classes
  - Generated code (protobuf, OpenAPI)
  - Configuration classes
  - Framework boilerplate
  - Third-party integrations (mock instead)

sonar.coverage.exclusions=\
  **/dto/**,\
  **/entity/**,\
  **/config/**,\
  **/generated/**,\
  **/*Application.java
```

### Pre-commit Hooks for Quality

```json
// .husky/pre-commit (Node.js with Husky + lint-staged)
// package.json
{
  "lint-staged": {
    "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
    "*.{css,json,md}": ["prettier --write"]
  }
}
```

```yaml
# .pre-commit-config.yaml (Python)
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: check-yaml
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
```

### Technical Debt Management

```
Prioritization framework:
  1. Security vulnerabilities (fix immediately)
  2. Bugs in critical paths (fix in current sprint)
  3. Code smells blocking feature work (fix when touching that code)
  4. General tech debt (allocate 15-20% of sprint capacity)

Sprint allocation:
  - 80% feature work
  - 10% tech debt reduction
  - 10% maintenance/upgrades

Tracking:
  - SonarQube dashboard: track debt over time
  - Tag issues with "tech-debt" label
  - Review debt trend in retrospectives
```

---

## 11. SonarLint

### Overview

SonarLint is an IDE plugin that provides real-time feedback on code quality issues as you write code.

### Supported IDEs

| IDE | Plugin | Features |
|-----|--------|----------|
| VS Code | SonarLint extension | Real-time, connected mode |
| IntelliJ IDEA | SonarLint plugin | Full analysis, taint tracking |
| Eclipse | SonarLint plugin | Real-time analysis |
| Visual Studio | SonarLint extension | .NET focused |

### Connected Mode

```
Connected mode syncs rules from your SonarQube/SonarCloud server:

Benefits:
  - Same rules in IDE as in CI (no surprises)
  - Suppress false positives carry over
  - Quality profile changes auto-sync
  - Taint analysis (track data flow from server analysis)
  - Secret detection

Setup (VS Code):
  1. Install SonarLint extension
  2. Open Settings → SonarLint: Connected Mode
  3. Add connection: URL + token
  4. Bind project: select organization → project

// .vscode/settings.json
{
  "sonarlint.connectedMode.connections.sonarqube": [
    {
      "serverUrl": "https://sonar.company.com",
      "token": "${env:SONAR_TOKEN}"
    }
  ],
  "sonarlint.connectedMode.project": {
    "connectionId": "company-sonar",
    "projectKey": "my-project"
  }
}
```

### SonarLint Features

```
Real-time detection:
  - Code smells as you type
  - Bugs highlighted immediately
  - Security hotspots flagged
  - Quick fixes suggested

Taint analysis (connected mode):
  - Server detects tainted data flow
  - SonarLint shows in IDE where tainted data enters
  - Traces flow through code to vulnerable sink

Secret detection:
  - AWS keys, GCP credentials, Azure tokens
  - Database connection strings
  - API keys, private keys
  - Works without connected mode
```

---

## 12. Scenario-Based Interview Questions

### Q1: "Quality gate failing on legacy project with 20% coverage - strategy?"

```
Answer:
1. DON'T try to add tests to all legacy code (waste of effort)
2. Configure "New Code Period" = Previous Version or Reference Branch
3. Set quality gate on NEW CODE only:
   - New code coverage ≥ 80%
   - New bugs = 0
   - New vulnerabilities = 0
4. For overall metrics, set realistic improving targets:
   - Month 1: overall ≥ 25%
   - Month 3: overall ≥ 35%
   - Month 6: overall ≥ 50%
5. When touching legacy code for features/bugs, add tests (Boy Scout Rule)
6. Identify critical paths, prioritize coverage there
7. Track trend in sprint retrospectives

Key principle: "Clean as You Code" - you can't fix the past overnight,
but you can ensure all new code meets standards.
```

### Q2: "Integrate SonarQube in existing CI/CD pipeline"

```
Answer:
Step 1: Setup SonarQube server
  - Docker/Kubernetes deployment
  - PostgreSQL database
  - Configure authentication (LDAP/SAML)

Step 2: Create project and generate token
  - Project key, quality profile, quality gate

Step 3: Add scanner to CI pipeline
  - Choose scanner type (CLI/Maven/Gradle/.NET)
  - Add sonar-project.properties or inline config
  - Store SONAR_TOKEN as CI secret

Step 4: Configure coverage import
  - Run tests with coverage (JaCoCo/Istanbul/coverage.py)
  - Point sonar to coverage report paths

Step 5: Add quality gate check
  - sonar.qualitygate.wait=true
  - Fail pipeline on gate failure

Step 6: Enable PR decoration (Developer Edition+)
  - ALM integration
  - Webhook for status updates

Step 7: Rollout
  - Start with warning mode (don't block)
  - Review initial results, tune false positives
  - After 2 weeks, enable blocking mode
```

### Q3: "Reduce 5000 code smells in a large codebase"

```
Answer:
1. DON'T create a "fix all code smells" epic (never works)
2. Categorize by severity and type:
   - Blocker/Critical: fix immediately (usually few)
   - Major: fix when touching that file
   - Minor/Info: low priority

3. Identify patterns:
   - If 2000 smells are "missing @Override" → bulk fix with IDE
   - If 500 are "unused imports" → auto-fix with formatter
   - Group by rule, fix high-count easy rules first

4. Strategy:
   - Week 1: Auto-fixable issues (formatting, imports) = -1500
   - Sprint allocation: 15% capacity for tech debt = -200/sprint
   - Boy Scout Rule: fix smells in files you touch = -100/sprint
   - Quality gate prevents new smells

5. Timeline: 5000 → manageable in 3-6 months without dedicated effort
```

### Q4: "SonarQube shows false positive - how to handle?"

```
Answer:
Options (in order of preference):
1. Mark as "False Positive" with comment explaining why
   - Persists across analyses
   - Doesn't affect metrics

2. Mark as "Won't Fix" (if it's valid but acceptable)
   - With justification comment
   - Review periodically

3. Exclude via sonar-project.properties
   - sonar.issue.ignore.multicriteria=e1
   - sonar.issue.ignore.multicriteria.e1.ruleKey=java:S1234
   - sonar.issue.ignore.multicriteria.e1.resourceKey=**/SpecificFile.java

4. Adjust quality profile
   - Deactivate rule if it produces many false positives
   - Or change severity

5. //NOSONAR comment (last resort)
   - Suppresses all issues on that line
   - Not recommended (too broad, no documentation)

Best practice: Document WHY it's a false positive, review quarterly.
```

### Q5: "Performance: SonarQube scan takes 45 minutes - optimize"

```
Answer:
1. Identify bottleneck:
   - Scanner side or server side?
   - Which phase is slow? (indexing, analysis, report upload)

2. Scanner optimizations:
   - Exclude unnecessary files: sonar.exclusions
   - Reduce scope: only analyze changed files (PR mode)
   - Increase scanner memory: SONAR_SCANNER_OPTS="-Xmx4g"
   - Use incremental analysis (if available)
   - Parallelize: sonar.cfamily.threads (C/C++)

3. Server optimizations:
   - Increase compute engine workers: sonar.ce.workerCount=4
   - More RAM for Elasticsearch: sonar.search.javaOpts
   - SSD storage for database and ES
   - Separate DB server

4. Architecture:
   - Split monorepo into multiple projects
   - Use branch analysis (only new code)
   - Schedule full analysis nightly, PR analysis on-demand
   - Consider Data Center Edition for horizontal scaling

5. Coverage report generation (often the real bottleneck):
   - Run only relevant tests for changed code
   - Parallel test execution
   - Cache test results
```

### Q6: "Design code quality strategy for a new team/project"

```
Answer:
Day 1:
  - Setup SonarQube/SonarCloud
  - Choose quality profile (start with "Sonar way")
  - Set strict quality gate (new code focus)
  - Install SonarLint for all developers

Week 1:
  - Configure CI integration
  - Setup coverage reporting
  - Enable PR decoration
  - Define exclusions (generated code, etc.)

Sprint 1:
  - Establish coding standards document
  - Configure linters (ESLint/Checkstyle/pylint)
  - Setup pre-commit hooks
  - First quality review

Ongoing:
  - Quality metrics in sprint dashboard
  - Monthly quality profile review
  - Quarterly tech debt review
  - Coverage targets in team goals
```

### Q7: "Custom rule needed for company-specific pattern"

```
Answer:
Options by complexity:

1. Semgrep custom rule (easiest):
   - Pattern-based, YAML definition
   - No compilation needed
   - Run alongside SonarQube

2. SonarQube XPath rule (XML/HTML):
   - Built-in template rules
   - Administration > Rules > Create Template

3. SonarQube regex rule:
   - For simple pattern detection
   - Rule templates in quality profile

4. Custom SonarQube plugin (most powerful):
   - Java-based plugin development
   - Full AST access
   - Deploy to extensions/plugins/
   - Requires rebuilding on SQ upgrades

5. CodeQL custom query:
   - Powerful semantic analysis
   - QL language (learning curve)
   - Great for data flow patterns
```

### Q8: "SonarQube vs CodeQL - when to use which?"

```
Answer:
Use SonarQube when:
  - Need combined quality + security analysis
  - Want maintainability/reliability metrics
  - Need quality gates for deployment
  - Coverage tracking
  - Technical debt management
  - Team dashboards and trends

Use CodeQL when:
  - Need deep semantic security analysis
  - Complex data flow / taint tracking
  - Custom vulnerability patterns
  - GitHub-native workflow
  - Open-source projects (free via GHAS)
  - Variant analysis (find pattern across repos)

Best practice: Use BOTH
  - SonarQube: daily quality + basic security
  - CodeQL: weekly deep security scans
  - They complement, not compete
```

### Q9: "Monorepo analysis configuration"

```
Answer:
Option A: Single SonarQube project
  sonar.projectKey=monorepo
  sonar.sources=services/api/src,services/web/src,libs/shared/src
  sonar.tests=services/api/test,services/web/test
  
  Pros: unified view, single quality gate
  Cons: slow, one failure blocks all

Option B: Multiple projects (recommended)
  # Run per service
  sonar-scanner \
    -Dsonar.projectKey=monorepo-api \
    -Dsonar.sources=services/api/src \
    -Dsonar.projectBaseDir=services/api

  Pros: independent gates, faster scans, clear ownership
  Cons: more configuration, separate dashboards

Option C: SonarQube Portfolio (Enterprise)
  - Group projects into portfolio
  - Aggregate metrics
  - Executive dashboard across all services

CI optimization for monorepos:
  - Detect changed services (path filter)
  - Only scan affected services
  - Cache scanner results
```

### Q10: "Implement security scanning pipeline (SAST + DAST + SCA)"

```
Answer:
Layered approach:

Layer 1 - Developer (shift-left):
  - SonarLint in IDE (real-time SAST)
  - Pre-commit: gitleaks (secrets)
  - NPM audit / pip-audit (local SCA)

Layer 2 - CI Pipeline:
  - SAST: SonarQube + Semgrep
  - SCA: Snyk/Dependabot
  - Container: Trivy
  - IaC: Checkov/tfsec
  - Secrets: GitLeaks

Layer 3 - Pre-deploy:
  - DAST: OWASP ZAP baseline scan
  - Integration security tests

Layer 4 - Production:
  - DAST: Full ZAP scan (scheduled)
  - Runtime: Falco, WAF logs
  - Continuous SCA monitoring (Snyk monitor)

Gate criteria:
  - SAST: No critical/high in new code
  - SCA: No critical CVEs, high CVEs < 30 days to fix
  - DAST: No high findings
  - Secrets: Zero tolerance
```

### Q11: "Technical debt prioritization strategy"

```
Answer:
Framework - Impact vs Effort matrix:

High Impact, Low Effort (DO FIRST):
  - Security vulnerabilities
  - Auto-fixable code smells (bulk fix)
  - Dead code removal
  - Unused dependency cleanup

High Impact, High Effort (PLAN):
  - Architectural issues
  - Major refactoring
  - Framework upgrades
  - Test coverage for critical paths

Low Impact, Low Effort (OPPORTUNISTIC):
  - Naming conventions
  - Minor code smells
  - Documentation
  - Boy Scout Rule candidates

Low Impact, High Effort (SKIP/DEFER):
  - Cosmetic refactoring
  - Over-engineering
  - Rewriting working legacy code

Metrics to track:
  - Debt ratio trend (should decrease)
  - New debt added per sprint
  - Debt paid per sprint
  - Ratio: debt paid / debt added > 1.0
```

### Q12: "Design pre-commit hooks for code quality"

```
Answer:
Multi-layer pre-commit strategy:

Fast checks (< 5 seconds, every commit):
  - Formatting (prettier, black, gofmt)
  - Lint quick rules (no-console, unused imports)
  - Secret detection (gitleaks)
  - File size limits
  - Merge conflict markers

Medium checks (< 30 seconds, pre-push):
  - Full lint (ESLint, pylint)
  - Type checking (tsc --noEmit, mypy)
  - Unit tests for changed files

Slow checks (CI only, not local):
  - Full test suite
  - SonarQube analysis
  - DAST scans
  - Build verification

Implementation:
  Node.js: husky + lint-staged
  Python: pre-commit framework
  Go: golangci-lint + lefthook
  General: lefthook (polyglot)

Key principle: Keep pre-commit FAST (< 10s) or developers will skip them.
Use --no-verify escape hatch for emergencies only.
```

### Q13: "Coverage shows 85% but critical bugs still escape - why?"

```
Answer:
Coverage ≠ Quality of tests. Common issues:

1. No assertions (tests run code but don't verify behavior)
2. Happy path only (no error/edge case testing)
3. Mocking too much (testing mocks, not real behavior)
4. Integration gaps (units work alone, fail together)
5. Missing boundary tests (off-by-one, null, empty)

Solutions:
  - Mutation testing (PIT for Java, Stryker for JS)
    → Modifies code, checks if tests catch it
  - Assertion density metric (assertions per test)
  - Branch coverage not just line coverage
  - Review test quality in code reviews
  - Add property-based testing for edge cases
  - Cognitive complexity in tests (keep tests simple)
```

### Q14: "Migration from legacy linting to SonarQube"

```
Answer:
Phased approach:

Phase 1 (Week 1-2): Parallel run
  - Install SonarQube alongside existing tools
  - Run both in CI (SonarQube in non-blocking mode)
  - Compare findings, identify overlap/gaps

Phase 2 (Week 3-4): Tune and align
  - Map existing lint rules to SonarQube rules
  - Adjust quality profile to match current standards
  - Mark existing issues as "accepted" baseline
  - Fix false positives

Phase 3 (Month 2): Cutover
  - Enable quality gate (blocking mode)
  - Remove redundant lint rules (avoid double-reporting)
  - Keep formatting tools (Prettier/Black) - SonarQube doesn't format
  - Keep type checkers (TypeScript/mypy) - complementary

Phase 4 (Ongoing): Expand
  - Add security rules
  - Enable branch analysis
  - Setup PR decoration
  - Add SonarLint to developer workflow
```

### Q15: "Multi-language project quality strategy"

```
Answer:
Example: Microservices with Java backend, React frontend, Python ML service

Shared:
  - Single SonarQube instance
  - Consistent quality gate across services
  - Unified dashboard (Portfolio view)

Per-language configuration:
  Java:
    - Profile: Sonar way + custom security rules
    - Coverage: JaCoCo
    - Additional: SpotBugs for bytecode analysis
    
  TypeScript/React:
    - Profile: Sonar way + accessibility rules
    - Coverage: Jest + Istanbul
    - Additional: ESLint for React-specific rules
    
  Python:
    - Profile: Sonar way + type annotation rules
    - Coverage: pytest-cov
    - Additional: mypy for type checking, bandit for security

Quality gates (same for all):
  - New code coverage ≥ 80%
  - New bugs = 0
  - New vulnerabilities = 0
  - New duplications < 3%

CI: Each service has its own pipeline with language-specific scanner config.
```

---

## Quick Reference

### Essential sonar-project.properties

```properties
sonar.projectKey=org_project
sonar.sources=src
sonar.tests=test
sonar.exclusions=**/node_modules/**,**/vendor/**,**/*.min.js
sonar.coverage.exclusions=**/test/**,**/config/**
sonar.cpd.exclusions=**/dto/**
sonar.qualitygate.wait=true
sonar.sourceEncoding=UTF-8
```

### Key CLI Commands

```bash
# Basic scan
sonar-scanner -Dsonar.token=$SONAR_TOKEN

# Maven
mvn clean verify sonar:sonar

# Gradle
./gradlew sonar

# .NET
dotnet sonarscanner begin /k:"key" && dotnet build && dotnet sonarscanner end

# Check quality gate via API
curl -s -u $SONAR_TOKEN: \
  "$SONAR_HOST/api/qualitygates/project_status?projectKey=my-project" \
  | jq '.projectStatus.status'
```

### SonarQube API Examples

```bash
# Get project metrics
curl -s -u token: "http://sonar:9000/api/measures/component?\
component=my-project&\
metricKeys=bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density"

# Search issues
curl -s -u token: "http://sonar:9000/api/issues/search?\
componentKeys=my-project&\
severities=CRITICAL,BLOCKER&\
statuses=OPEN"

# Create project
curl -s -u token: -X POST "http://sonar:9000/api/projects/create?\
name=My+Project&\
project=my-project-key"
```
