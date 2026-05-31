# GitHub Copilot Custom Agents Setup

This directory contains custom agent definitions for GitHub Copilot that specialize in different aspects of the software development lifecycle.

## Available Agents

### 🏗️ @sdlc-architect
**Complete SDLC automation agent**

Handles the entire development lifecycle from PRD to deployment:
- PRD Analysis
- Architecture Design (HLD/LLD)
- Database Design
- Code Generation (Python, TypeScript, Go, Java, Rust)
- Security Review
- Code Review
- Deployment Configuration

**Example Usage:**
```
@sdlc-architect Analyze this PRD and create a complete system design with code:

[paste PRD content]
```

### 💻 @code-architect  
**Codebase analysis and code generation**

Analyzes existing codebases and generates new code following established patterns:
- Technology stack identification
- Architecture pattern detection
- Code generation following existing conventions
- Integration with existing components

**Example Usage:**
```
@code-architect Analyze the codebase in src/ and generate a new payment service that follows our existing patterns
```

### 🔒 @security-reviewer
**Security analysis and vulnerability fixing**

Comprehensive security review:
- SAST (Static Analysis)
- Dependency vulnerability scanning
- OWASP Top 10 compliance
- Threat modeling
- Security fixes

**Example Usage:**
```
@security-reviewer Review this code for security vulnerabilities and suggest fixes:

[paste code]
```

### 🚀 @deployment-engineer
**Deployment and infrastructure configuration**

Creates deployment artifacts:
- CI/CD pipelines (GitHub Actions, GitLab CI)
- Kubernetes manifests
- Terraform/IaC
- Monitoring and alerting setup
- Deployment strategies (Blue/Green, Canary)

**Example Usage:**
```
@deployment-engineer Generate a complete deployment setup for this Python FastAPI service with Kubernetes and GitHub Actions
```

### 🧪 @test-engineer
**Test generation and quality assurance**

Generates comprehensive test suites:
- Unit tests
- Integration tests
- E2E tests
- Load tests
- Test fixtures and mocks

**Example Usage:**
```
@test-engineer Generate comprehensive unit and integration tests for this service:

[paste code]
```

### 👀 @pr-reviewer
**Code review and quality assessment**

Performs thorough code reviews:
- Code quality scoring
- Architecture compliance
- Performance analysis
- Security validation
- NFR verification

**Example Usage:**
```
@pr-reviewer Review this pull request and provide detailed feedback:

[paste PR diff or code]
```

---

## Installation

### Option 1: Using VS Code Settings (Recommended)

1. Open VS Code Settings (⌘+, on Mac, Ctrl+, on Windows)
2. Search for "GitHub Copilot"
3. Find "GitHub Copilot: Custom Agents"
4. Click "Edit in settings.json"
5. Add this configuration:

```json
{
  "github.copilot.advanced": {
    "customAgents": {
      "configPath": "/Users/harsh.kumar01/Documents/learning/learning-conv/System-Design/AI-ML/system-design-agent/.github/copilot/agents.json"
    }
  }
}
```

### Option 2: Workspace Settings

Create or edit `.vscode/settings.json` in your project root:

```json
{
  "github.copilot.advanced": {
    "customAgents": {
      "configPath": "${workspaceFolder}/.github/copilot/agents.json"
    }
  }
}
```

### Option 3: Import via Copilot UI

1. Open GitHub Copilot Chat in VS Code
2. Click on the "Agent" dropdown (as shown in your screenshot)
3. Select "Configure Custom Agents..."
4. Click "Import from file"
5. Select `.github/copilot/agents.json`

---

## Usage Examples

### Complete Feature Development

```
@sdlc-architect I need to build a payment processing feature. Here's the PRD:

## Payment Processing Feature

### Requirements
- Integration with Stripe API
- Support credit cards and ACH
- Store transaction history
- Send payment confirmation emails
- Handle payment failures and retries

### Non-Functional Requirements
- 99.9% availability
- p95 latency < 500ms
- PCI-DSS compliant
- Handle 1000 transactions/minute

Generate complete implementation with:
1. System architecture (HLD/LLD)
2. Database schema
3. Production-ready code
4. Tests
5. Deployment configuration
6. Security review
```

### Extending Existing Codebase

```
@code-architect Our codebase is in src/services/. We use:
- Python 3.11 with FastAPI
- PostgreSQL with SQLAlchemy
- Redis for caching
- Repository pattern

Generate a new NotificationService that:
- Sends emails via SendGrid
- Sends SMS via Twilio
- Stores notification history in DB
- Follows our existing code patterns
```

### Security Audit

```
@security-reviewer Perform a comprehensive security review of our authentication service:

[paste authentication code or file path]

Check for:
- OWASP Top 10 vulnerabilities
- JWT token security
- Password hashing implementation
- Rate limiting
- Input validation
```

### Deployment Setup

```
@deployment-engineer Create a complete deployment setup for our microservices:

Services:
- API Gateway (Node.js)
- Order Service (Python FastAPI)
- Payment Service (Python FastAPI)
- Notification Service (Go)

Requirements:
- Deploy to AWS EKS
- Use blue/green deployment
- Include monitoring with Prometheus/Grafana
- CI/CD with GitHub Actions
- Auto-scaling based on CPU
```

### Test Coverage Improvement

```
@test-engineer Our OrderService needs better test coverage. Current code:

[paste service code]

Generate:
1. Unit tests for all public methods
2. Integration tests for database operations
3. E2E tests for the complete order flow
4. Load tests for handling 1000 req/s
5. Test fixtures and factories
```

### Code Review

```
@pr-reviewer Review this pull request for our payment service:

Changes:
- Added refund functionality
- Implemented webhook handling
- Updated payment status tracking

[paste PR diff or changed files]

Validate:
- Code quality and best practices
- Security considerations
- Performance implications
- Test coverage
- Documentation updates
```

---

## Agent Chaining

You can chain agents for complex workflows:

```
Step 1 - Design:
@sdlc-architect Create HLD and LLD for a real-time chat application

Step 2 - Code:
@code-architect Generate the message service based on the above design

Step 3 - Tests:
@test-engineer Create comprehensive tests for the generated message service

Step 4 - Security:
@security-reviewer Review the message service for security issues

Step 5 - Deploy:
@deployment-engineer Create deployment configuration for the chat application
```

---

## Tips for Better Results

### 1. Provide Context
```
Good:
@sdlc-architect Our e-commerce platform uses microservices (Python/FastAPI, PostgreSQL, Redis). 
Create a recommendation engine that suggests products based on browsing history.

Better than:
@sdlc-architect Create a recommendation engine
```

### 2. Specify Technology Stack
```
@code-architect Generate a user authentication service using:
- Python 3.11
- FastAPI
- PostgreSQL
- JWT for tokens
- Bcrypt for passwords
- Redis for session store
```

### 3. Include Non-Functional Requirements
```
@sdlc-architect Design a file storage service with:
- Support 10M users
- 1TB storage per user
- 99.99% availability
- Regional data compliance (GDPR)
- End-to-end encryption
```

### 4. Reference Existing Code
```
@code-architect Look at src/services/user_service.py for our patterns. 
Generate an order_service.py that follows the same structure.
```

### 5. Request Specific Formats
```
@deployment-engineer Create Kubernetes manifests in separate files:
- deployment.yaml
- service.yaml
- ingress.yaml
- hpa.yaml
- configmap.yaml
```

---

## Troubleshooting

### Agents Not Appearing

1. **Check VS Code version**: Ensure you have the latest GitHub Copilot extension
2. **Verify file path**: Make sure `agents.json` path in settings is correct
3. **Reload VS Code**: Press ⌘+Shift+P (Ctrl+Shift+P) → "Reload Window"
4. **Check JSON syntax**: Validate `agents.json` is valid JSON

### Agent Not Responding as Expected

1. **Be more specific**: Provide detailed context and requirements
2. **Check agent capabilities**: Each agent specializes in specific areas
3. **Use appropriate agent**: Choose the right agent for your task
4. **Provide examples**: Show existing code patterns you want followed

### Performance Issues

1. **Break down requests**: Don't ask for everything at once
2. **Use agent chaining**: Complete one phase before moving to next
3. **Limit context size**: Don't paste entire large files

---

## Customization

You can customize agent prompts by editing `.github/copilot/agents.json`:

```json
{
  "id": "my-custom-agent",
  "name": "My Custom Agent",
  "description": "Does something specific",
  "prompt": "Your custom system prompt here...",
  "conversationStarters": [
    "Example question 1",
    "Example question 2"
  ]
}
```

---

## Integration with Existing Workflow

### 1. Feature Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/payment-processing

# 2. Use @sdlc-architect for design
# Get HLD, LLD, DB schema

# 3. Review designs manually
# Approve architecture

# 4. Use @code-architect for implementation
# Generate code following patterns

# 5. Use @test-engineer for tests
# Get comprehensive test coverage

# 6. Use @security-reviewer before committing
# Fix any security issues

# 7. Use @pr-reviewer before creating PR
# Self-review to catch issues

# 8. Create PR and request human review
git add .
git commit -m "feat: Add payment processing"
git push origin feature/payment-processing
```

### 2. Code Review Workflow

```bash
# Reviewer uses @pr-reviewer
# Get initial automated review

# Human reviewer adds additional feedback
# Focus on business logic and domain knowledge

# Developer addresses feedback
# Uses agents to help fix issues
```

### 3. Security Audit Workflow

```bash
# Periodic security audits
@security-reviewer Audit our authentication module in src/auth/

# Review results
# Prioritize critical/high issues

# Use @code-architect to implement fixes
# Verify fixes with @security-reviewer
```

---

## Best Practices

1. **Always Human Review**: Agents assist, humans decide
2. **Iterative Approach**: Start with design, then implement
3. **Test Agent Output**: Run generated code, validate results
4. **Security First**: Always run security review
5. **Document Decisions**: Record why you chose agent recommendations
6. **Version Control**: Commit agent-generated artifacts
7. **Continuous Learning**: Observe what works, refine your prompts

---

## Support

For issues or questions:
- Check [IMPLEMENTATION_GUIDE.md](../../IMPLEMENTATION_GUIDE.md)
- Review [EXTENDED_AUTONOMOUS_AGENT.md](../../EXTENDED_AUTONOMOUS_AGENT.md)
- See examples in `output/` directory
