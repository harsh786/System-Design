# IAM Roles & Amazon Cognito - Complete Guide

## 1. IAM Fundamentals

### What is IAM (Identity and Access Management)

IAM is AWS's centralized service for controlling **who** (authentication) can do **what** (authorization) on **which resources**. It's the security backbone of every AWS account.

Key characteristics:
- **Global service** - not regional; users, roles, policies are available across all regions
- **Eventually consistent** - changes propagate but may take seconds
- **Free** - no charge for IAM itself
- **Integrated with every AWS service**

### Principal Types

| Principal | Description | Credentials |
|-----------|-------------|-------------|
| **Root User** | Account owner, unrestricted access | Email + password + MFA |
| **IAM Users** | Individual identities within account | Username/password, access keys |
| **IAM Roles** | Assumed identity with temporary credentials | Temporary security tokens (STS) |
| **Federated Users** | External identities (corporate, social) | Temporary credentials via federation |
| **AWS Services** | Services acting on your behalf | Service assumes a role |

### Authentication vs Authorization

```
Authentication ("Who are you?")
├── Username + Password (console)
├── Access Key ID + Secret Access Key (CLI/API)
├── Temporary Security Credentials (STS tokens)
└── MFA token (additional factor)

Authorization ("What can you do?")
├── IAM Policies (JSON documents)
├── Resource-based Policies
├── Permission Boundaries
├── Service Control Policies (SCPs)
└── Session Policies
```

### IAM is Global

- IAM entities (users, groups, roles, policies) are not tied to any region
- IAM endpoint: `iam.amazonaws.com` (single global endpoint)
- ARN format: `arn:aws:iam::123456789012:user/username` (no region field)
- STS has regional endpoints but IAM itself is global

---

## 2. IAM Policies Deep Dive

### Policy Types

```
┌─────────────────────────────────────────────────────────────┐
│                    IAM Policy Types                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Identity-based Policies                                  │
│    ├── AWS Managed Policies (created by AWS)                │
│    ├── Customer Managed Policies (created by you)           │
│    └── Inline Policies (embedded in user/group/role)        │
│                                                             │
│ 2. Resource-based Policies (attached to resources)          │
│    ├── S3 Bucket Policy                                     │
│    ├── SQS Queue Policy                                     │
│    ├── KMS Key Policy                                       │
│    └── Lambda Function Policy                               │
│                                                             │
│ 3. Permission Boundaries (max permissions for IAM entity)   │
│                                                             │
│ 4. Service Control Policies (SCPs - AWS Organizations)      │
│                                                             │
│ 5. Session Policies (passed during AssumeRole/Federation)   │
│                                                             │
│ 6. Access Control Lists (ACLs - legacy, cross-account)      │
└─────────────────────────────────────────────────────────────┘
```

### Policy Structure

```json
{
  "Version": "2012-10-17",
  "Id": "optional-policy-id",
  "Statement": [
    {
      "Sid": "OptionalStatementId",
      "Effect": "Allow | Deny",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::my-bucket/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    }
  ]
}
```

**Field explanations:**
- `Version` - Always use `"2012-10-17"` (enables policy variables, newer features)
- `Statement` - Array of permission statements
- `Sid` - Optional human-readable identifier
- `Effect` - `Allow` or `Deny` (explicit deny always wins)
- `Principal` - Who the policy applies to (resource-based policies only)
- `Action` - API operations (`service:Action`)
- `Resource` - ARN(s) of resources the action applies to
- `Condition` - Optional constraints

### Policy Evaluation Logic

```
Request comes in
       │
       ▼
┌──────────────┐     ┌─────────┐
│ Explicit Deny│────▶│ DENIED  │
│  anywhere?   │ Yes └─────────┘
└──────┬───────┘
       │ No
       ▼
┌──────────────┐     ┌─────────┐
│  SCP allows? │────▶│ DENIED  │
│ (if in Org)  │ No  └─────────┘
└──────┬───────┘
       │ Yes
       ▼
┌──────────────────┐     ┌─────────┐
│ Permission        │────▶│ DENIED  │
│ Boundary allows?  │ No  └─────────┘
│ (if set)          │
└──────┬───────────┘
       │ Yes
       ▼
┌──────────────────┐     ┌─────────┐
│ Session policy    │────▶│ DENIED  │
│ allows? (if set)  │ No  └─────────┘
└──────┬───────────┘
       │ Yes
       ▼
┌──────────────────────────────────┐     ┌─────────┐
│ Identity-based OR Resource-based │────▶│ DENIED  │
│ policy explicitly allows?        │ No  └─────────┘
└──────────────┬───────────────────┘
               │ Yes
               ▼
          ┌─────────┐
          │ ALLOWED │
          └─────────┘
```

**Key rule:** For cross-account access, BOTH the identity-based policy in the source account AND the resource-based policy in the target account must allow the action.

### Condition Keys

| Condition Key | Use Case |
|---------------|----------|
| `aws:SourceIp` | Restrict by IP range |
| `aws:RequestedRegion` | Restrict by region |
| `aws:MultiFactorAuthPresent` | Require MFA |
| `aws:MultiFactorAuthAge` | MFA token age in seconds |
| `aws:PrincipalTag/key` | Tag on the calling principal |
| `aws:ResourceTag/key` | Tag on the resource |
| `aws:PrincipalOrgID` | Organization ID of caller |
| `aws:SourceVpc` | VPC the request comes from |
| `aws:SourceVpce` | VPC endpoint the request uses |
| `aws:CurrentTime` | Current time for time-based access |
| `s3:prefix` | S3-specific: key prefix |
| `ec2:ResourceTag/key` | EC2-specific: instance tags |

**Example: Require MFA for destructive actions**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAllWithMFA",
      "Effect": "Deny",
      "Action": [
        "ec2:TerminateInstances",
        "ec2:StopInstances"
      ],
      "Resource": "*",
      "Condition": {
        "BoolIfExists": {
          "aws:MultiFactorAuthPresent": "false"
        }
      }
    }
  ]
}
```

**Example: Restrict to specific regions**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyOutsideAllowedRegions",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "eu-west-1"]
        }
      }
    }
  ]
}
```

### Policy Variables

Policy variables allow dynamic values in policies:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowUserOwnFolder",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::company-bucket/home/${aws:username}/*"
    },
    {
      "Sid": "AllowTeamFolder",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::company-bucket/teams/${aws:PrincipalTag/team}/*"
    }
  ]
}
```

Common variables:
- `${aws:username}` - IAM username
- `${aws:userid}` - Unique ID of the principal
- `${aws:PrincipalTag/key}` - Tag value on the principal
- `${aws:FederatedProvider}` - Federation provider
- `${s3:prefix}` - S3 request prefix
- `${cognito-identity.amazonaws.com:sub}` - Cognito identity ID

### AWS Managed vs Customer Managed vs Inline

| Aspect | AWS Managed | Customer Managed | Inline |
|--------|-------------|-----------------|--------|
| Created by | AWS | You | You |
| Reusable | Yes | Yes | No (embedded) |
| Versioned | Yes (by AWS) | Yes (up to 5) | No |
| Central updates | AWS updates | You update | Per-entity update |
| Use case | Common permissions | Org-specific | Strict 1:1 mapping |
| Deletable | No | Yes | Deleted with entity |

**Best practice:** Prefer Customer Managed > AWS Managed > Inline

---

## 3. IAM Roles

### What is a Role

An IAM Role is an identity with:
- **No long-term credentials** (no password, no permanent access keys)
- **Temporary security credentials** issued by STS when the role is assumed
- **A trust policy** defining who can assume the role
- **Permission policies** defining what the role can do

```
┌─────────────────────────────────────┐
│            IAM Role                  │
├─────────────────────────────────────┤
│ Trust Policy (who can assume)       │
│ + Permission Policies (what to do)  │
│ + Session duration (1-12 hours)     │
│ + Tags                              │
└─────────────────────────────────────┘
         │
         │ AssumeRole API
         ▼
┌─────────────────────────────────────┐
│ Temporary Credentials               │
│ - AccessKeyId                       │
│ - SecretAccessKey                   │
│ - SessionToken                      │
│ - Expiration                        │
└─────────────────────────────────────┘
```

### Trust Policy + Permission Policy

**Trust Policy (who can assume):**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Permission Policy (what the role can do):**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::app-data-bucket/*"
    }
  ]
}
```

### Role Types

#### Service Roles

Roles that AWS services assume to act on your behalf.

**EC2 Instance Role:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Lambda Execution Role:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**ECS Task Role:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

#### Cross-Account Roles

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::111111111111:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "unique-external-id-12345"
        }
      }
    }
  ]
}
```

**OrganizationAccountAccessRole** - automatically created in member accounts, allows management account full access.

#### Federation Roles

- **SAML:** Corporate IdP (Active Directory) → `AssumeRoleWithSAML`
- **Web Identity:** Social IdPs → `AssumeRoleWithWebIdentity` (prefer Cognito)
- **Custom Broker:** For non-SAML corporate IdPs

#### Service-Linked Roles

- Created automatically by AWS services
- Cannot modify permissions (defined by the service)
- Named: `AWSServiceRoleForServiceName`
- Examples: `AWSServiceRoleForElasticLoadBalancing`, `AWSServiceRoleForAutoScaling`

### AssumeRole Variants

| API | Use Case | Who Calls |
|-----|----------|-----------|
| `AssumeRole` | Cross-account, service roles | IAM users, roles |
| `AssumeRoleWithSAML` | SAML federation | After SAML assertion |
| `AssumeRoleWithWebIdentity` | Web/mobile (use Cognito instead) | After IdP token |
| `GetSessionToken` | MFA-protected API access | IAM users |
| `GetFederationToken` | Custom identity broker | IAM users (broker) |

### Session Duration

- **Default:** 1 hour
- **Maximum:** 12 hours (configurable per role)
- **Role chaining:** Limited to 1 hour maximum (when role A assumes role B)
- **Console sessions:** 1-12 hours

### External ID (Confused Deputy Problem)

**The problem:** A third-party service (e.g., monitoring tool) has a role in YOUR account. An attacker could tell the same service to access YOUR role, because the service has permission.

**The solution:** External ID - a secret shared between you and the third party.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::THIRD_PARTY_ACCOUNT:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "your-unique-external-id"
        }
      }
    }
  ]
}
```

### Instance Profiles

- An instance profile is a **container** for an IAM role attached to an EC2 instance
- When you create a role in the console for EC2, an instance profile with the same name is auto-created
- Via CLI/API, you must create them separately:

```bash
aws iam create-instance-profile --instance-profile-name MyProfile
aws iam add-role-to-instance-profile --instance-profile-name MyProfile --role-name MyRole
aws ec2 associate-iam-instance-profile --instance-id i-1234567890 \
  --iam-instance-profile Name=MyProfile
```

### PassRole Permission

`iam:PassRole` controls who can assign roles to AWS services. Without it, users could escalate privileges by attaching admin roles to resources.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::123456789012:role/EC2-S3-ReadOnly",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "ec2.amazonaws.com"
        }
      }
    }
  ]
}
```

---

## 4. IAM Security Best Practices

### Root Account Security

1. **Enable MFA immediately** (hardware key preferred)
2. **Never create access keys** for root
3. **Use only for account-level tasks:**
   - Change account settings (name, email, root password)
   - Change AWS support plan
   - Restore IAM user permissions (if locked out)
   - Close the account
4. **Set up billing alerts**
5. **Store credentials in a physical safe**

### Least Privilege Principle

```
Start with zero permissions
        │
        ▼
Add only what's needed for the specific task
        │
        ▼
Use IAM Access Analyzer to find unused permissions
        │
        ▼
Regularly review and remove unused permissions
        │
        ▼
Use permission boundaries for delegation
```

### MFA Types

| Type | Description | Example |
|------|-------------|---------|
| Virtual MFA | TOTP app | Google Authenticator, Authy |
| U2F Security Key | Hardware USB key | YubiKey |
| Hardware MFA | Dedicated device | Gemalto token |

### IAM Access Analyzer

- **External access analysis:** Find resources shared with external entities
- **Unused access analysis:** Find unused roles, permissions, access keys
- **Policy validation:** Check policies for errors and best practices
- **Policy generation:** Generate least-privilege policies from CloudTrail logs

### IAM Policy Simulator

- Test policies without deploying them
- Available at: `https://policysim.aws.amazon.com`
- Test for specific users/roles against specific actions
- Useful for debugging "access denied" errors

---

## 5. IAM Advanced

### Identity Federation

#### SAML 2.0 Federation

```
Corporate User → Corporate IdP (AD) → SAML Assertion
                                              │
                                              ▼
                                    AWS STS (AssumeRoleWithSAML)
                                              │
                                              ▼
                                    Temporary Credentials
                                              │
                                              ▼
                                    Access AWS Resources
```

Steps:
1. Set up trust between AWS and corporate IdP (upload IdP metadata to IAM)
2. Create IAM role with SAML trust policy
3. User authenticates with corporate IdP
4. IdP returns SAML assertion
5. User calls `AssumeRoleWithSAML` with the assertion
6. STS returns temporary credentials

#### Web Identity Federation (Without Cognito)

```
User → Login with Google/Facebook → Get IdP Token
                                          │
                                          ▼
                              AssumeRoleWithWebIdentity
                                          │
                                          ▼
                              Temporary AWS Credentials
```

**AWS recommends using Cognito Identity Pools instead** (handles token exchange, guest access, role mapping).

#### Custom Identity Broker

For organizations with IdPs that don't support SAML:

1. User authenticates against corporate IdP
2. Custom broker validates credentials
3. Broker calls `GetFederationToken` or `AssumeRole`
4. Returns temporary credentials to user

#### IAM Identity Center (AWS SSO)

- **Centralized access** across all AWS accounts in an organization
- **Single sign-on** portal for users
- **Built-in identity store** or connect Active Directory
- **Permission Sets** - define role policies, auto-deployed to accounts
- **ABAC support** with attribute-based access

### STS (Security Token Service)

| API Call | Description |
|----------|-------------|
| `AssumeRole` | Get temp creds for a role (cross-account, service) |
| `AssumeRoleWithSAML` | After SAML authentication |
| `AssumeRoleWithWebIdentity` | After web IdP auth (use Cognito) |
| `GetSessionToken` | MFA-protected temp creds for IAM user |
| `GetFederationToken` | Temp creds for federated user (custom broker) |
| `GetCallerIdentity` | Returns identity of the caller (useful for debugging) |
| `DecodeAuthorizationMessage` | Decode encoded auth failure messages |

### Tag-Based Access Control (ABAC)

ABAC uses tags on both principals and resources for authorization:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAccessToOwnResources",
      "Effect": "Allow",
      "Action": ["ec2:StartInstances", "ec2:StopInstances"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "ec2:ResourceTag/team": "${aws:PrincipalTag/team}"
        }
      }
    }
  ]
}
```

**ABAC vs RBAC:**
- RBAC: Create roles per team/function, attach policies listing specific resources
- ABAC: Create fewer policies using tags, scales better with many resources
- ABAC advantage: No policy update needed when new resources are created (if tagged correctly)

### Resource-Based vs Role-Based Access (Cross-Account)

| Aspect | Resource-Based Policy | Cross-Account Role |
|--------|----------------------|-------------------|
| Mechanism | Policy on target resource | Role in target account |
| Caller identity | Retains original identity | Becomes the role |
| Works with | S3, SQS, SNS, KMS, Lambda | Any service |
| Principal in CloudTrail | Original caller | Role session |
| Use when | Need to keep caller identity | Service doesn't support resource policies |

---

## 6. Amazon Cognito Overview

### What is Cognito

Amazon Cognito provides:
- **Authentication** - verify user identity
- **Authorization** - control access to AWS resources
- **User management** - sign-up, sign-in, profiles, MFA
- **Token-based access** - JWT tokens for APIs
- **AWS credential vending** - temporary credentials for direct AWS access

### User Pools vs Identity Pools

```
┌──────────────────────────────────────────────────────────────┐
│                        Amazon Cognito                         │
├─────────────────────────────┬────────────────────────────────┤
│       USER POOLS            │       IDENTITY POOLS           │
│    (Authentication)         │      (Authorization)           │
├─────────────────────────────┼────────────────────────────────┤
│ • User directory            │ • AWS credential vending       │
│ • Sign-up / Sign-in        │ • Exchange tokens for          │
│ • Returns JWT tokens        │   temporary AWS credentials    │
│ • Managed user store        │ • Supports authenticated +     │
│ • Social/SAML federation    │   unauthenticated access       │
│ • MFA, password policies    │ • Fine-grained IAM access      │
│ • Custom auth flows         │ • Works with any IdP token     │
│                             │                                │
│ Output: ID/Access/Refresh   │ Output: AWS AccessKey/Secret/  │
│         JWT tokens          │         SessionToken           │
└─────────────────────────────┴────────────────────────────────┘
```

**Common pattern:** User Pool (authentication) → Identity Pool (AWS authorization)

---

## 7. Cognito User Pools

### Features

- **Sign-up/Sign-in:** Email, phone, username, or custom alias
- **Password policies:** Min length, require uppercase/lowercase/numbers/symbols
- **MFA:** SMS or TOTP (software token)
- **Email/Phone verification:** Required/optional
- **Account recovery:** Email, phone, admin
- **Custom attributes:** Add custom fields to user profiles
- **Groups:** Organize users, map to IAM roles, set precedence
- **Hosted UI:** Pre-built sign-in/sign-up pages with OAuth support

### Authentication Flows

| Flow | Use Case | Description |
|------|----------|-------------|
| `USER_SRP_AUTH` | Default client-side | Secure Remote Password (never sends password) |
| `USER_PASSWORD_AUTH` | Migration trigger | Sends password (use with TLS only) |
| `CUSTOM_AUTH` | Custom challenges | Lambda-driven (OTP, CAPTCHA, etc.) |
| `ADMIN_USER_PASSWORD_AUTH` | Server-side | Server uses admin credentials |
| `REFRESH_TOKEN_AUTH` | Token refresh | Exchange refresh token for new tokens |

### Tokens

| Token | Purpose | Contains | Typical Use |
|-------|---------|----------|-------------|
| **ID Token** | User identity | User attributes, email, groups | Frontend display, API Gateway |
| **Access Token** | Authorization | Scopes, groups, client_id | API access, OAuth flows |
| **Refresh Token** | Get new tokens | Opaque (not JWT) | Silent re-authentication |

**Token lifetimes:**
- ID Token: 5 min - 1 day (default 1 hour)
- Access Token: 5 min - 1 day (default 1 hour)
- Refresh Token: 1 hour - 10 years (default 30 days)

### Lambda Triggers

```
User Journey:
                                                  
Sign-Up ──► Pre Sign-up ──► Post Confirmation
                │
Authentication ──► Pre Authentication ──► Post Authentication
                │
Custom Auth ──► Define Auth Challenge ──► Create Auth Challenge
                                       ──► Verify Auth Challenge
                │
Token Gen ──► Pre Token Generation (customize claims)
                │
Migration ──► User Migration (from legacy system)
                │
Messages ──► Custom Message (customize emails/SMS)
```

**Pre Token Generation example use case:** Add custom claims, suppress claims, modify group membership in token.

### OAuth 2.0 Flows

| Flow | Use Case | Tokens Returned |
|------|----------|----------------|
| **Authorization Code** | Server-side apps | Code → exchange for tokens |
| **Authorization Code + PKCE** | SPAs, mobile | Code + verifier → tokens |
| **Implicit** | Legacy SPAs (deprecated) | Tokens directly in URL |
| **Client Credentials** | Machine-to-machine | Access token (no user) |

### Hosted UI Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/login` | Sign-in page |
| `/signup` | Sign-up page |
| `/oauth2/authorize` | Start OAuth flow |
| `/oauth2/token` | Exchange code for tokens |
| `/oauth2/userInfo` | Get user attributes |
| `/oauth2/revoke` | Revoke refresh token |
| `/logout` | Sign out and clear session |

### Resource Servers

Define custom scopes for your APIs:

```
Resource Server: api.myapp.com
├── Scope: api.myapp.com/read
├── Scope: api.myapp.com/write
└── Scope: api.myapp.com/admin
```

App clients request specific scopes; access token contains granted scopes.

### Advanced Security

- **Adaptive Authentication:** Risk-based MFA (new device, new location, impossible travel)
- **Compromised Credentials Detection:** Block sign-in if credentials found in breaches
- **Risk levels:** Low, Medium, High → Allow, Optional MFA, Block
- Requires Advanced Security Mode enabled (additional cost)

---

## 8. Cognito Identity Pools (Federated Identities)

### Flow

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────┐
│   User   │───▶│  Authenticate │───▶│   Identity   │───▶│  AWS    │
│          │    │  (get token)  │    │    Pool      │    │Resources│
└──────────┘    └──────────────┘    └──────────────┘    └─────────┘
                                           │
                                    Exchange token
                                    for AWS creds
                                    (via STS)
```

Detailed flow:
1. User authenticates with an IdP (Cognito User Pool, Google, SAML, etc.)
2. User receives token from IdP
3. Application sends token to Cognito Identity Pool
4. Identity Pool validates token and returns identity ID
5. Identity Pool calls STS `AssumeRoleWithWebIdentity`
6. Application receives temporary AWS credentials (AccessKey, Secret, SessionToken)
7. Application uses credentials to access AWS services directly

### Supported Identity Providers

- Cognito User Pools
- Facebook, Google, Apple, Amazon
- SAML 2.0 providers
- OpenID Connect (OIDC) providers
- Custom developer-authenticated identities

### Authenticated vs Unauthenticated Roles

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::public-assets/*"
    }
  ]
}
```
↑ Unauthenticated (guest) role - minimal permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::user-data/${cognito-identity.amazonaws.com:sub}/*"
    }
  ]
}
```
↑ Authenticated role - scoped to user's own data

### Role Selection

| Method | Description |
|--------|-------------|
| **Default** | All users get the same authenticated/unauthenticated role |
| **Token-based** | Role ARN embedded in IdP token (Cognito User Pool groups) |
| **Rules-based** | Match claims (email, custom attributes) to roles |

**Token-based example:** Cognito User Pool group "admins" has IAM role attached → users in that group get admin role from Identity Pool.

### Fine-Grained Access with Policy Variables

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"],
      "Resource": "arn:aws:dynamodb:us-east-1:123456789012:table/UserData",
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${cognito-identity.amazonaws.com:sub}"]
        }
      }
    }
  ]
}
```

This ensures each user can only access their own DynamoDB items (partition key = identity ID).

### Enhanced Flow vs Basic (Classic) Flow

| Aspect | Enhanced (Simplified) | Basic (Classic) |
|--------|----------------------|-----------------|
| STS call | Made by Cognito | Made by your app |
| Role selection | Token/Rules/Default | Your app decides |
| Recommended | Yes | Legacy |
| Scope down | Via role selection | Via custom policy in code |

### Use Case: Mobile App Accessing S3

```
Mobile App → Sign in with User Pool → Get ID Token
    │
    ▼
Send ID Token to Identity Pool → Get AWS Credentials
    │
    ▼
Use credentials to upload to S3: s3://bucket/${identity-id}/photos/*
```

---

## 9. Cognito Integration Patterns

### API Gateway + Cognito Authorizer

```
Client → (Bearer token) → API Gateway → Cognito User Pool (validate)
                                │
                         Token valid? ──► Invoke Lambda / Backend
```

- API Gateway validates the token directly with User Pool
- No Lambda authorizer needed
- Can check scopes in the access token
- Returns 401 if token invalid/expired

### ALB + Cognito (OIDC Authentication)

```
Client → ALB → Cognito Hosted UI (if not authenticated)
                    │
              User signs in
                    │
              ALB gets tokens ──► Forward request to target
                                  (with user claims in headers)
```

- ALB handles the full OIDC flow
- Injects user info headers (`x-amzn-oidc-data`, `x-amzn-oidc-identity`)
- Works with any OIDC-compatible IdP (not just Cognito)
- Great for internal apps that need SSO

### S3 + Cognito Identity Pool

```
Client → Authenticate → Identity Pool → AWS Credentials
    │
    ▼
Direct S3 upload with temporary credentials
(restricted to user's prefix via IAM policy)
```

### AppSync + Cognito

- Native integration as authorization mode
- Can use User Pool tokens or Identity Pool credentials
- Field-level authorization with `@auth` directive
- Group-based access control

### CloudFront + Lambda@Edge + Cognito

```
Client → CloudFront → Lambda@Edge (Viewer Request)
                            │
                      Validate JWT token
                      (check signature, expiry)
                            │
                      Valid? ──► Forward to origin
                      Invalid? ──► 401 / Redirect to login
```

Use case: Protect static content (S3) behind Cognito authentication.

---

## 10. Cognito vs Auth0 vs Firebase Auth vs IAM Identity Center

| Feature | Cognito | Auth0 | Firebase Auth | IAM Identity Center |
|---------|---------|-------|---------------|-------------------|
| **Primary use** | AWS-native auth | Universal auth | Mobile/web apps | AWS multi-account SSO |
| **User directory** | Yes | Yes | Yes | Yes (or external) |
| **Social login** | Yes | Yes | Yes | Limited |
| **SAML/OIDC** | Yes | Yes | No native SAML | Yes |
| **AWS credential vending** | Yes (Identity Pools) | No (need custom) | No | Yes (Permission Sets) |
| **Custom UI** | Hosted UI + custom | Universal Login + custom | Firebase UI + custom | AWS portal only |
| **MFA** | SMS, TOTP | SMS, TOTP, Push, WebAuthn | SMS, TOTP | MFA via IdP |
| **Lambda triggers** | Yes (8 triggers) | Yes (Actions/Rules) | Cloud Functions | Limited |
| **Machine-to-machine** | Client credentials | Yes | No | No |
| **Pricing** | Free tier: 50K MAU | Free: 7.5K MAU | Free: unlimited* | Free with AWS Org |
| **Customization** | Medium | High | Medium | Low |
| **Multi-tenant** | Manual | Built-in | Manual | Built-in (accounts) |
| **Compliance** | SOC, HIPAA | SOC, HIPAA, PCI | SOC | SOC, HIPAA |

### When to Use Which

| Scenario | Recommendation |
|----------|---------------|
| AWS-native app needing direct AWS resource access | **Cognito** |
| Complex enterprise B2B with many IdPs | **Auth0** |
| Mobile app with Firebase backend | **Firebase Auth** |
| Multi-account AWS organization SSO | **IAM Identity Center** |
| Startup, AWS-only, cost-sensitive | **Cognito** |
| Need passwordless, WebAuthn, advanced MFA | **Auth0** |
| Internal workforce AWS access | **IAM Identity Center** |

---

## 11. Scenario-Based Interview Questions

### Q1: Design authentication for microservices with different user types

**Scenario:** E-commerce platform with customers, merchants, and admins.

**Solution:**
```
┌─────────────────────────────────────────────────────────┐
│ Cognito User Pool                                       │
│ ├── Group: customers (default role)                     │
│ ├── Group: merchants (elevated permissions)             │
│ └── Group: admins (full access)                         │
│                                                         │
│ Custom attributes: user_type, merchant_id, tier         │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│ API Gateway with Cognito Authorizer                     │
│ ├── /orders/* - customers, merchants, admins            │
│ ├── /products/* - merchants (check scope), admins       │
│ └── /admin/* - admins only (check group in Lambda)      │
└─────────────────────────────────────────────────────────┘
```

Use pre-token-generation Lambda to inject claims based on user type. Backend Lambdas check `cognito:groups` claim for authorization.

---

### Q2: Cross-account access pattern for shared services

**Scenario:** Central logging account (222) needs to pull logs from production account (111).

**Solution:**

In production account (111), create role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::222222222222:role/LogCollectorRole"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

In logging account (222), LogCollectorRole has permission:
```json
{
  "Effect": "Allow",
  "Action": "sts:AssumeRole",
  "Resource": "arn:aws:iam::111111111111:role/CrossAccountLogsRole"
}
```

---

### Q3: Fine-grained access control (user can only access own data)

**Solution using Cognito Identity Pool + DynamoDB:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query"],
      "Resource": "arn:aws:dynamodb:*:*:table/UserData",
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${cognito-identity.amazonaws.com:sub}"]
        }
      }
    }
  ]
}
```

Table design: Partition key = Cognito identity ID. Each user can only access rows where PK matches their identity.

---

### Q4: Confused Deputy Problem - Explain and Prevent

**Problem:**
- You give a third-party service (Account X) permission to assume a role in your account
- An attacker also uses Account X's service
- Attacker tells Account X to assume YOUR role (since Account X has permission)
- Account X unknowingly accesses your resources on behalf of the attacker

**Prevention - External ID:**
```json
{
  "Condition": {
    "StringEquals": {
      "sts:ExternalId": "unique-id-only-you-and-vendor-know"
    }
  }
}
```

The attacker doesn't know the external ID, so Account X's attempt to assume the role on attacker's behalf fails.

---

### Q5: Design SSO for organization with 50 AWS accounts

**Solution: IAM Identity Center**

```
┌──────────────────────────────────────────┐
│ AWS Organization (Management Account)    │
│                                          │
│ IAM Identity Center                      │
│ ├── Identity Source: Corporate AD (SAML) │
│ ├── Permission Sets:                     │
│ │   ├── AdminAccess                      │
│ │   ├── DeveloperAccess                  │
│ │   ├── ReadOnlyAccess                   │
│ │   └── BillingAccess                    │
│ └── Assignments:                         │
│     ├── DevTeam → DeveloperAccess → Dev accounts     │
│     ├── OpsTeam → AdminAccess → All accounts         │
│     └── Finance → BillingAccess → Management account │
└──────────────────────────────────────────┘
```

Users access single portal → see assigned accounts → click to get temporary credentials.

---

### Q6: Mobile app needs to upload to S3 - design the auth flow

```
1. User opens app → signs in via Cognito User Pool (email + password)
2. App receives ID Token + Access Token + Refresh Token
3. App sends ID Token to Cognito Identity Pool
4. Identity Pool returns temporary AWS credentials
5. App uses AWS SDK with temp creds to upload directly to S3
6. IAM policy restricts upload to: s3://bucket/${cognito-id}/uploads/*
```

**Why not through API Gateway?**
- Large file uploads (API Gateway has 10MB payload limit)
- Direct S3 upload is more efficient
- S3 multipart upload supported

---

### Q7: API with free tier and paid tier users

**Solution:**

```
Cognito User Pool:
├── Group: free_tier (API rate: 100 req/day)
├── Group: paid_basic (API rate: 10,000 req/day)  
└── Group: paid_premium (API rate: unlimited)

API Gateway:
├── Usage Plan: Free (100 req/day, 10 req/sec burst)
├── Usage Plan: Basic (10,000 req/day, 100 req/sec burst)
└── Usage Plan: Premium (no limits)

Lambda Authorizer:
├── Validate Cognito token
├── Check group claim
├── Return API key mapped to usage plan
└── Cache authorization for 5 min
```

Alternative: Use Cognito custom attributes for tier, check in Lambda authorizer, map to API Gateway usage plans.

---

### Q8: User locked out of root account - recovery process

1. Go to AWS sign-in page → click "Forgot password"
2. AWS sends reset link to root email address
3. If email access lost:
   - Contact AWS Support via alternate support channel
   - Prove account ownership (billing info, account ID, registered address)
4. If MFA device lost:
   - Use MFA recovery options if configured
   - Contact AWS Support with identity verification
5. **Prevention:**
   - Store root credentials securely (physical safe)
   - Use hardware MFA with backup codes stored separately
   - Document root email access recovery path

---

### Q9: Implement MFA for critical operations only

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAllActions",
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*"
    },
    {
      "Sid": "DenyCriticalWithoutMFA",
      "Effect": "Deny",
      "Action": [
        "ec2:TerminateInstances",
        "rds:DeleteDBInstance",
        "s3:DeleteBucket",
        "iam:DeleteUser",
        "iam:CreateUser",
        "iam:AttachUserPolicy"
      ],
      "Resource": "*",
      "Condition": {
        "BoolIfExists": {
          "aws:MultiFactorAuthPresent": "false"
        }
      }
    }
  ]
}
```

User can do normal work without MFA. Destructive actions require MFA-authenticated session (`GetSessionToken` with MFA code).

---

### Q10: Design RBAC vs ABAC for multi-team environment

**RBAC approach:**
- Role per team: `TeamA-Developer`, `TeamB-Developer`, `TeamA-Admin`
- Each role explicitly lists resource ARNs
- Problem: Must update policies when new resources added

**ABAC approach:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ec2:*"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "ec2:ResourceTag/team": "${aws:PrincipalTag/team}",
          "ec2:ResourceTag/environment": "${aws:PrincipalTag/environment}"
        }
      }
    }
  ]
}
```

**ABAC advantages:** Scales without policy changes. Tag new resources with `team=A` → team A automatically has access. One policy covers all teams.

**Recommendation:** Use ABAC for dynamic, scaling environments. RBAC for strict compliance where explicit resource lists are required.

---

### Q11: Lambda needs cross-account DynamoDB access

**Account A (Lambda)** → **Account B (DynamoDB)**

**Option 1: Cross-account role (recommended)**
```
Lambda (Account A) with execution role that can sts:AssumeRole
    │
    ▼
Assumes role in Account B (trust policy allows Account A's Lambda role)
    │
    ▼
Uses temporary credentials to access DynamoDB in Account B
```

**Option 2: Resource-based policy**
DynamoDB doesn't support resource-based policies → must use Option 1.

Lambda code:
```python
import boto3

sts = boto3.client('sts')
response = sts.assume_role(
    RoleArn='arn:aws:iam::ACCOUNT_B:role/DynamoDBAccessRole',
    RoleSessionName='lambda-cross-account'
)

credentials = response['Credentials']
dynamodb = boto3.resource('dynamodb',
    aws_access_key_id=credentials['AccessKeyId'],
    aws_secret_access_key=credentials['SecretAccessKey'],
    aws_session_token=credentials['SessionToken']
)
table = dynamodb.Table('MyTable')
```

---

### Q12: Audit who accessed what in AWS

**Solution:**

```
┌─────────────────────────────────────────────────────┐
│ CloudTrail (all API calls)                          │
│ ├── Management events: CreateBucket, RunInstances   │
│ ├── Data events: GetObject, PutItem                 │
│ └── Insights: unusual API activity                  │
├─────────────────────────────────────────────────────┤
│ → S3 bucket (long-term storage, lifecycle)          │
│ → CloudWatch Logs (real-time alerting)              │
│ → Athena (ad-hoc SQL queries over CloudTrail)       │
│ → Security Hub (centralized findings)               │
└─────────────────────────────────────────────────────┘

IAM Access Analyzer:
├── External access findings
├── Unused access findings
└── Policy validation

Config Rules:
├── iam-root-access-key-check
├── iam-user-mfa-enabled
├── iam-user-unused-credentials-check
└── iam-policy-no-statements-with-admin-access
```

---

### Q13: Temporary elevated access (break-glass)

**Scenario:** Developer needs production DB access for emergency debugging.

**Solution:**
1. Dedicated role: `EmergencyProductionAccess` with time-limited permissions
2. Trust policy requires MFA + specific group membership
3. Session duration: 1 hour maximum
4. CloudTrail + SNS alert when role is assumed
5. Post-incident: review CloudTrail logs for all actions taken

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "Bool": {"aws:MultiFactorAuthPresent": "true"},
        "StringEquals": {
          "aws:PrincipalTag/oncall": "true"
        }
      }
    }
  ]
}
```

---

### Q14: Secure API for both internal services and external users

```
External Users:
  → Cognito User Pool → Access Token → API Gateway (Cognito Authorizer)

Internal Services (machine-to-machine):
  → Cognito App Client (client_credentials grant) → Access Token
  → OR IAM auth (SigV4) → API Gateway (IAM Authorizer)

API Gateway:
  → Multiple authorizers on different routes
  → /public/* → Cognito authorizer
  → /internal/* → IAM authorizer
```

---

### Q15: Prevent privilege escalation

**Problem:** Developer with `iam:CreateRole` could create an admin role and assume it.

**Solution: Permission Boundary**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCreateRoleWithBoundary",
      "Effect": "Allow",
      "Action": ["iam:CreateRole", "iam:AttachRolePolicy"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "iam:PermissionsBoundary": "arn:aws:iam::123456789012:policy/DeveloperBoundary"
        }
      }
    }
  ]
}
```

Developers can create roles but MUST attach the permission boundary. The boundary limits maximum possible permissions regardless of what policies are attached to the new role.

---

## Key Takeaways for Exam / Interview

1. **IAM Roles > IAM Users** for applications - always use temporary credentials
2. **Cognito User Pool = Authentication**, **Identity Pool = AWS Credentials**
3. **Explicit Deny always wins** in policy evaluation
4. **Cross-account:** Both sides must allow (identity policy + resource policy or role)
5. **External ID** solves the confused deputy problem
6. **Permission Boundaries** prevent privilege escalation in delegated admin scenarios
7. **ABAC** scales better than RBAC for dynamic environments
8. **IAM Identity Center** is the answer for multi-account workforce SSO
9. **Role chaining** has a 1-hour session limit
10. **iam:PassRole** controls who can assign roles to services (privilege escalation prevention)
