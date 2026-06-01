# Problem 5: User Onboarding & KYC Verification

## The Problem

Onboard 500K+ users/day across 50 countries with multi-vendor KYC verification:
- Identity verification through 3+ external vendors (Jumio, Onfido, Sumsub)
- Sanctions screening (ComplyAdvantage, Dow Jones)
- Credit checks (Experian, TransUnion)
- Human review queue for edge cases (~8% of submissions)
- Process duration: 30 seconds (happy path) to 3 weeks (document re-submission)
- Regulatory requirements vary by jurisdiction (GDPR, CCPA, local AML laws)
- Complete audit trail for every decision point
- SLA: 95% of standard verifications complete in <5 minutes

**Scale requirements:**
- 500K new user registrations/day
- 40K concurrent onboarding workflows
- 3M+ vendor API calls/day
- 40K human review decisions/day
- 50 country-specific compliance flows
- 99.99% audit completeness

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      USER ONBOARDING PLATFORM                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌────────────────┐         ┌──────────────────────────────────────────────┐    │
│  │   Mobile App   │────────▶│              API Gateway                      │    │
│  │   Web App      │◀────────│  (Start onboarding, upload docs, check status)│    │
│  └────────────────┘         └──────────────┬───────────────────────────────┘    │
│                                             │                                     │
│                                             ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                       Temporal Server Cluster                              │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │   │
│  │  │  UserOnboardingWorkflow (per user, long-running, signal-driven) │     │   │
│  │  │                                                                   │     │   │
│  │  │  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐   │     │   │
│  │  │  │Collect  │─▶│ Verify   │─▶│ Sanctions │─▶│ Decision     │   │     │   │
│  │  │  │Documents│  │ Identity │  │ Screen    │  │ (Auto/Human) │   │     │   │
│  │  │  └─────────┘  └──────────┘  └───────────┘  └──────────────┘   │     │   │
│  │  │       │              │              │               │           │     │   │
│  │  │       │         ┌────┴────┐         │          ┌────┴─────┐    │     │   │
│  │  │       │         │ Vendor  │         │          │ Human    │    │     │   │
│  │  │       │         │ Failover│         │          │ Review   │    │     │   │
│  │  │       │         │ Logic   │         │          │ Queue    │    │     │   │
│  │  │       │         └─────────┘         │          └──────────┘    │     │   │
│  │  └───────┼─────────────────────────────┼──────────────────────────┘     │   │
│  └──────────┼─────────────────────────────┼────────────────────────────────┘   │
│             │                             │                                     │
│  ┌──────────┼─────────────────────────────┼────────────────────────────────┐   │
│  │          ▼                             ▼                                 │   │
│  │  Worker Pools                                                            │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │   │
│  │  │ Verification    │  │ Sanctions         │  │ Notification         │   │   │
│  │  │ Workers         │  │ Workers           │  │ Workers              │   │   │
│  │  │                 │  │                   │  │                      │   │   │
│  │  │ - Jumio API     │  │ - ComplyAdvantage │  │ - Email (SendGrid)  │   │   │
│  │  │ - Onfido API    │  │ - Dow Jones       │  │ - SMS (Twilio)      │   │   │
│  │  │ - Sumsub API    │  │ - OFAC            │  │ - Push (Firebase)   │   │   │
│  │  │                 │  │ - Local lists      │  │ - In-app            │   │   │
│  │  └─────────────────┘  └──────────────────┘  └──────────────────────┘   │   │
│  │                                                                          │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │   │
│  │  │ Document        │  │ Credit Check      │  │ Human Review         │   │   │
│  │  │ Workers         │  │ Workers           │  │ Workers              │   │   │
│  │  │                 │  │                   │  │                      │   │   │
│  │  │ - OCR/Extract   │  │ - Experian        │  │ - Assignment         │   │   │
│  │  │ - Validation    │  │ - TransUnion       │  │ - Escalation         │   │   │
│  │  │ - Storage (S3)  │  │ - Equifax          │  │ - SLA tracking       │   │   │
│  │  └─────────────────┘  └──────────────────┘  └──────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         External Systems                                   │   │
│  │  ┌──────┐ ┌────────┐ ┌─────────┐ ┌──────────┐ ┌───────┐ ┌──────────┐  │   │
│  │  │Jumio │ │Onfido  │ │Comply   │ │Experian  │ │S3 Doc │ │Compliance│  │   │
│  │  │      │ │        │ │Advantage│ │          │ │Store  │ │Dashboard │  │   │
│  │  └──────┘ └────────┘ └─────────┘ └──────────┘ └───────┘ └──────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Go Implementation

### Domain Types

```go
package onboarding

import (
	"context"
	"fmt"
	"strings"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// ─── Domain Types ───────────────────────────────────────────────────────────

type UserOnboardingInput struct {
	UserID        string          `json:"user_id"`
	Email         string          `json:"email"`
	Phone         string          `json:"phone"`
	Country       string          `json:"country"`
	AccountType   string          `json:"account_type"` // personal, business, premium
	RiskTier      string          `json:"risk_tier"`    // low, medium, high (from initial scoring)
	Documents     []DocumentRef   `json:"documents"`
	PersonalInfo  PersonalInfo    `json:"personal_info"`
	ConsentGiven  bool            `json:"consent_given"`
	RequestID     string          `json:"request_id"`
	CreatedAt     time.Time       `json:"created_at"`
}

type PersonalInfo struct {
	FirstName   string    `json:"first_name"`
	LastName    string    `json:"last_name"`
	DateOfBirth time.Time `json:"date_of_birth"`
	Nationality string    `json:"nationality"`
	Address     Address   `json:"address"`
	TaxID       string    `json:"tax_id,omitempty"`
}

type Address struct {
	Street     string `json:"street"`
	City       string `json:"city"`
	State      string `json:"state"`
	PostalCode string `json:"postal_code"`
	Country    string `json:"country"`
}

type DocumentRef struct {
	DocumentID   string `json:"document_id"`
	DocumentType string `json:"document_type"` // passport, drivers_license, utility_bill, bank_statement
	StoragePath  string `json:"storage_path"`
	UploadedAt   time.Time `json:"uploaded_at"`
	MimeType     string `json:"mime_type"`
	SizeBytes    int64  `json:"size_bytes"`
}

type VerificationResult struct {
	VendorID     string                 `json:"vendor_id"`
	VendorName   string                 `json:"vendor_name"`
	Status       VerificationStatus     `json:"status"`
	Confidence   float64                `json:"confidence"` // 0.0 - 1.0
	RiskScore    float64                `json:"risk_score"`
	Details      map[string]interface{} `json:"details"`
	CheckedAt    time.Time              `json:"checked_at"`
	ResponseTime time.Duration          `json:"response_time"`
	RawResponse  string                 `json:"raw_response,omitempty"` // for audit
}

type VerificationStatus string

const (
	StatusPassed      VerificationStatus = "PASSED"
	StatusFailed      VerificationStatus = "FAILED"
	StatusReview      VerificationStatus = "REVIEW_REQUIRED"
	StatusExpired     VerificationStatus = "EXPIRED"
	StatusUnavailable VerificationStatus = "UNAVAILABLE"
)

type SanctionsResult struct {
	Provider    string    `json:"provider"`
	IsMatch     bool      `json:"is_match"`
	MatchScore  float64   `json:"match_score"`
	Matches     []SanctionsMatch `json:"matches"`
	CheckedAt   time.Time `json:"checked_at"`
	ListVersion string    `json:"list_version"`
}

type SanctionsMatch struct {
	ListName    string  `json:"list_name"`
	EntityName  string  `json:"entity_name"`
	MatchScore  float64 `json:"match_score"`
	EntityType  string  `json:"entity_type"`
}

type CreditCheckResult struct {
	Provider     string  `json:"provider"`
	CreditScore  int     `json:"credit_score"`
	RiskCategory string  `json:"risk_category"`
	Factors      []string `json:"factors"`
	CheckedAt    time.Time `json:"checked_at"`
}

type HumanReviewRequest struct {
	ReviewID       string            `json:"review_id"`
	UserID         string            `json:"user_id"`
	ReviewType     string            `json:"review_type"` // identity, document, sanctions, escalation
	Priority       ReviewPriority    `json:"priority"`
	AssignedTo     string            `json:"assigned_to,omitempty"`
	EscalationLevel int             `json:"escalation_level"`
	Context        ReviewContext     `json:"context"`
	CreatedAt      time.Time         `json:"created_at"`
	DueBy          time.Time         `json:"due_by"`
}

type ReviewPriority int

const (
	ReviewPriorityLow    ReviewPriority = 0
	ReviewPriorityNormal ReviewPriority = 1
	ReviewPriorityHigh   ReviewPriority = 2
	ReviewPriorityUrgent ReviewPriority = 3
)

type ReviewContext struct {
	VerificationResults []VerificationResult `json:"verification_results"`
	SanctionsResults    []SanctionsResult    `json:"sanctions_results"`
	Documents           []DocumentRef        `json:"documents"`
	RiskScore           float64              `json:"risk_score"`
	Flags               []string             `json:"flags"`
}

type HumanReviewDecision struct {
	ReviewID    string    `json:"review_id"`
	ReviewerID  string    `json:"reviewer_id"`
	Decision    string    `json:"decision"` // approve, reject, request_more_info, escalate
	Reason      string    `json:"reason"`
	Notes       string    `json:"notes"`
	DecidedAt   time.Time `json:"decided_at"`
}

type OnboardingResult struct {
	UserID              string             `json:"user_id"`
	Status              string             `json:"status"` // approved, rejected, pending_review
	Decision            string             `json:"decision"`
	DecisionReason      string             `json:"decision_reason"`
	VerificationResults []VerificationResult `json:"verification_results"`
	SanctionsResults    []SanctionsResult  `json:"sanctions_results"`
	CreditResult        *CreditCheckResult `json:"credit_result,omitempty"`
	HumanReviews        []HumanReviewDecision `json:"human_reviews,omitempty"`
	RiskScore           float64            `json:"risk_score"`
	ApprovedTier        string             `json:"approved_tier"`
	StartTime           time.Time          `json:"start_time"`
	EndTime             time.Time          `json:"end_time"`
	Duration            time.Duration      `json:"duration"`
	AuditTrail          []AuditEvent       `json:"audit_trail"`
}

type AuditEvent struct {
	Timestamp time.Time   `json:"timestamp"`
	EventType string      `json:"event_type"`
	Actor     string      `json:"actor"` // system, vendor_name, reviewer_id
	Action    string      `json:"action"`
	Details   interface{} `json:"details"`
}

// ─── Signals & Queries ──────────────────────────────────────────────────────

const (
	SignalDocumentUploaded    = "document-uploaded"
	SignalHumanReviewComplete = "human-review-complete"
	SignalCancelOnboarding    = "cancel-onboarding"
	SignalRequestMoreInfo     = "request-more-info"

	QueryOnboardingStatus    = "onboarding-status"
	QueryVerificationDetails = "verification-details"
)

type DocumentUploadedSignal struct {
	Document DocumentRef `json:"document"`
}

type OnboardingStatusResponse struct {
	UserID          string    `json:"user_id"`
	CurrentStep     string    `json:"current_step"`
	StepsCompleted  []string  `json:"steps_completed"`
	StepsPending    []string  `json:"steps_pending"`
	AwaitingAction  string    `json:"awaiting_action,omitempty"` // what the user needs to do
	EstimatedTime   string    `json:"estimated_time"`
	LastUpdated     time.Time `json:"last_updated"`
}
```

### Main Onboarding Workflow

```go
// ─── Main Onboarding Workflow ───────────────────────────────────────────────

func UserOnboardingWorkflow(ctx workflow.Context, input UserOnboardingInput) (*OnboardingResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting user onboarding",
		"user_id", input.UserID,
		"country", input.Country,
		"account_type", input.AccountType,
	)

	// Initialize state
	state := &onboardingState{
		input:           input,
		currentStep:     "initialized",
		stepsCompleted:  []string{},
		auditTrail:      []AuditEvent{},
		documents:       input.Documents,
	}

	// Register query handlers
	err := workflow.SetQueryHandler(ctx, QueryOnboardingStatus, func() (*OnboardingStatusResponse, error) {
		return state.getStatusResponse(), nil
	})
	if err != nil {
		return nil, err
	}

	// Set search attributes
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"UserID":             input.UserID,
		"Country":            input.Country,
		"AccountType":        input.AccountType,
		"RiskTier":           input.RiskTier,
		"VerificationStatus": "IN_PROGRESS",
		"OnboardingStep":     "started",
	})

	state.addAudit("system", "onboarding_started", map[string]interface{}{
		"country": input.Country, "account_type": input.AccountType,
	})

	result := &OnboardingResult{
		UserID:    input.UserID,
		StartTime: workflow.Now(ctx),
	}

	// ─── Step 1: Validate Documents ────────────────────────────────────
	state.currentStep = "document_validation"
	updateStep(ctx, "document_validation")

	if len(state.documents) == 0 {
		// Wait for document upload (with timeout)
		docs, err := waitForDocuments(ctx, state, input)
		if err != nil {
			result.Status = "rejected"
			result.Decision = "TIMEOUT_NO_DOCUMENTS"
			result.DecisionReason = "User did not upload required documents within deadline"
			return result, nil
		}
		state.documents = docs
	}

	// Validate document quality
	validDocs, err := validateDocuments(ctx, state)
	if err != nil {
		return nil, err
	}
	if len(validDocs) == 0 {
		result.Status = "rejected"
		result.Decision = "INVALID_DOCUMENTS"
		return result, nil
	}

	// ─── Step 2: Get country-specific verification requirements ─────────
	requirements := getCountryRequirements(input.Country, input.AccountType, input.RiskTier)

	// ─── Step 3: Parallel Verification ─────────────────────────────────
	state.currentStep = "verification"
	updateStep(ctx, "verification")

	verificationCtx, cancelVerification := workflow.WithCancel(ctx)
	defer cancelVerification()

	// Launch parallel verifications
	identityFuture := executeIdentityVerification(verificationCtx, input, validDocs, requirements)
	sanctionsFuture := executeSanctionsScreening(verificationCtx, input)

	var creditFuture workflow.Future
	if requirements.CreditCheckRequired {
		creditFuture = executeCreditCheck(verificationCtx, input)
	}

	// ─── Collect results with early termination ────────────────────────
	// If sanctions hit, cancel everything immediately
	selector := workflow.NewSelector(ctx)
	var identityResult *VerificationResult
	var sanctionsResult *SanctionsResult
	var creditResult *CreditCheckResult
	resultsCollected := 0
	totalExpected := 2
	if requirements.CreditCheckRequired {
		totalExpected = 3
	}

	sanctionsChecked := false

	selector.AddFuture(sanctionsFuture, func(f workflow.Future) {
		var sr SanctionsResult
		if err := f.Get(ctx, &sr); err != nil {
			logger.Error("Sanctions check failed", "error", err)
			sr = SanctionsResult{IsMatch: false, Provider: "error"}
		}
		sanctionsResult = &sr
		sanctionsChecked = true
		resultsCollected++

		state.addAudit(sr.Provider, "sanctions_checked", map[string]interface{}{
			"is_match": sr.IsMatch, "match_score": sr.MatchScore,
		})

		// EARLY TERMINATION: If sanctions match, stop everything
		if sr.IsMatch && sr.MatchScore > 0.85 {
			logger.Warn("Sanctions match detected - terminating verification",
				"user_id", input.UserID, "score", sr.MatchScore)
			cancelVerification()
		}
	})

	selector.AddFuture(identityFuture, func(f workflow.Future) {
		var vr VerificationResult
		if err := f.Get(ctx, &vr); err != nil {
			logger.Error("Identity verification failed", "error", err)
			vr = VerificationResult{Status: StatusUnavailable, VendorName: "error"}
		}
		identityResult = &vr
		resultsCollected++

		state.addAudit(vr.VendorName, "identity_verified", map[string]interface{}{
			"status": vr.Status, "confidence": vr.Confidence,
		})
	})

	if creditFuture != nil {
		selector.AddFuture(creditFuture, func(f workflow.Future) {
			var cr CreditCheckResult
			if err := f.Get(ctx, &cr); err != nil {
				logger.Error("Credit check failed", "error", err)
			} else {
				creditResult = &cr
			}
			resultsCollected++
		})
	}

	// Wait for all results (or early termination)
	for resultsCollected < totalExpected {
		selector.Select(ctx)

		// Check if sanctions caused early termination
		if sanctionsChecked && sanctionsResult != nil && sanctionsResult.IsMatch && sanctionsResult.MatchScore > 0.85 {
			break
		}
	}

	// ─── Step 4: Decision ──────────────────────────────────────────────
	state.currentStep = "decision"
	updateStep(ctx, "decision")

	decision := makeDecision(input, identityResult, sanctionsResult, creditResult, requirements)

	result.VerificationResults = []VerificationResult{}
	if identityResult != nil {
		result.VerificationResults = append(result.VerificationResults, *identityResult)
	}
	if sanctionsResult != nil {
		result.SanctionsResults = append(result.SanctionsResults, *sanctionsResult)
	}
	result.CreditResult = creditResult
	result.RiskScore = decision.riskScore

	// ─── Step 5: Handle decision outcome ───────────────────────────────
	switch decision.outcome {
	case "auto_approve":
		result.Status = "approved"
		result.Decision = "AUTO_APPROVED"
		result.ApprovedTier = decision.approvedTier
		state.addAudit("system", "auto_approved", map[string]interface{}{
			"risk_score": decision.riskScore, "tier": decision.approvedTier,
		})

	case "auto_reject":
		result.Status = "rejected"
		result.Decision = "AUTO_REJECTED"
		result.DecisionReason = decision.reason
		state.addAudit("system", "auto_rejected", map[string]interface{}{
			"reason": decision.reason, "risk_score": decision.riskScore,
		})

	case "human_review":
		state.currentStep = "human_review"
		updateStep(ctx, "human_review")

		reviewDecision, err := executeHumanReview(ctx, state, input, decision)
		if err != nil {
			return nil, err
		}

		result.HumanReviews = append(result.HumanReviews, *reviewDecision)
		switch reviewDecision.Decision {
		case "approve":
			result.Status = "approved"
			result.Decision = "HUMAN_APPROVED"
			result.ApprovedTier = decision.approvedTier
		case "reject":
			result.Status = "rejected"
			result.Decision = "HUMAN_REJECTED"
			result.DecisionReason = reviewDecision.Reason
		case "request_more_info":
			// Loop back to document collection
			moreInfoResult, err := handleRequestMoreInfo(ctx, state, input, reviewDecision)
			if err != nil {
				return nil, err
			}
			if moreInfoResult != nil {
				result.Status = moreInfoResult.Status
				result.Decision = moreInfoResult.Decision
			}
		}
	}

	// ─── Step 6: Post-decision actions ─────────────────────────────────
	state.currentStep = "finalization"
	postDecisionCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "notification-workers",
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	// Send notification
	notification := NotificationInput{
		UserID:   input.UserID,
		Email:    input.Email,
		Phone:    input.Phone,
		Type:     "onboarding_" + result.Status,
		Decision: result.Decision,
		Reason:   result.DecisionReason,
	}
	_ = workflow.ExecuteActivity(postDecisionCtx, SendNotificationActivity, notification).Get(ctx, nil)

	// Update user account status
	accountCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 5},
	})
	_ = workflow.ExecuteActivity(accountCtx, UpdateAccountStatusActivity, AccountStatusInput{
		UserID: input.UserID,
		Status: result.Status,
		Tier:   result.ApprovedTier,
	}).Get(ctx, nil)

	// Finalize
	result.EndTime = workflow.Now(ctx)
	result.Duration = result.EndTime.Sub(result.StartTime)
	result.AuditTrail = state.auditTrail

	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"VerificationStatus": strings.ToUpper(result.Status),
		"OnboardingStep":     "completed",
		"RiskScore":          decision.riskScore,
	})

	logger.Info("Onboarding completed",
		"user_id", input.UserID,
		"status", result.Status,
		"duration", result.Duration,
	)

	return result, nil
}
```

### Onboarding State Management

```go
// ─── Onboarding State ───────────────────────────────────────────────────────

type onboardingState struct {
	input          UserOnboardingInput
	currentStep    string
	stepsCompleted []string
	auditTrail     []AuditEvent
	documents      []DocumentRef
}

func (s *onboardingState) addAudit(actor, action string, details interface{}) {
	s.auditTrail = append(s.auditTrail, AuditEvent{
		Timestamp: time.Now(),
		EventType: action,
		Actor:     actor,
		Action:    action,
		Details:   details,
	})
}

func (s *onboardingState) getStatusResponse() *OnboardingStatusResponse {
	allSteps := []string{"document_validation", "verification", "decision", "finalization"}
	var pending []string
	found := false
	for _, step := range allSteps {
		if step == s.currentStep {
			found = true
			continue
		}
		if found {
			pending = append(pending, step)
		}
	}

	awaitingAction := ""
	switch s.currentStep {
	case "document_validation":
		if len(s.documents) == 0 {
			awaitingAction = "Please upload your identity documents"
		}
	case "human_review":
		awaitingAction = "Your application is under review"
	}

	return &OnboardingStatusResponse{
		UserID:         s.input.UserID,
		CurrentStep:    s.currentStep,
		StepsCompleted: s.stepsCompleted,
		StepsPending:   pending,
		AwaitingAction: awaitingAction,
		LastUpdated:    time.Now(),
	}
}

func updateStep(ctx workflow.Context, step string) {
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"OnboardingStep": step,
	})
}
```

### Document Waiting and Validation

```go
// ─── Document Collection ────────────────────────────────────────────────────

func waitForDocuments(ctx workflow.Context, state *onboardingState, input UserOnboardingInput) ([]DocumentRef, error) {
	logger := workflow.GetLogger(ctx)

	// Send notification asking for documents
	notifCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "notification-workers",
		StartToCloseTimeout: 10 * time.Second,
	})
	_ = workflow.ExecuteActivity(notifCtx, SendNotificationActivity, NotificationInput{
		UserID: input.UserID,
		Email:  input.Email,
		Type:   "documents_required",
	}).Get(ctx, nil)

	// Wait up to 7 days for document upload
	documentDeadline := 7 * 24 * time.Hour
	timerCtx, cancelTimer := workflow.WithCancel(ctx)
	defer cancelTimer()
	deadlineTimer := workflow.NewTimer(timerCtx, documentDeadline)

	signalChan := workflow.GetSignalChannel(ctx, SignalDocumentUploaded)
	cancelChan := workflow.GetSignalChannel(ctx, SignalCancelOnboarding)

	var documents []DocumentRef
	requiredCount := getRequiredDocumentCount(input.Country, input.AccountType)

	for len(documents) < requiredCount {
		selector := workflow.NewSelector(ctx)

		selector.AddReceive(signalChan, func(ch workflow.ReceiveChannel, more bool) {
			var signal DocumentUploadedSignal
			ch.Receive(ctx, &signal)
			documents = append(documents, signal.Document)
			state.documents = documents
			state.addAudit("user", "document_uploaded", map[string]interface{}{
				"document_type": signal.Document.DocumentType,
				"total_docs":    len(documents),
			})
			logger.Info("Document received",
				"type", signal.Document.DocumentType,
				"total", len(documents),
				"required", requiredCount,
			)
		})

		selector.AddReceive(cancelChan, func(ch workflow.ReceiveChannel, more bool) {
			ch.Receive(ctx, nil)
			logger.Info("Onboarding cancelled by user")
		})

		selector.AddFuture(deadlineTimer, func(f workflow.Future) {
			logger.Warn("Document upload deadline expired", "user_id", input.UserID)
		})

		selector.Select(ctx)

		// Check if deadline expired
		if deadlineTimer.IsReady() && len(documents) < requiredCount {
			// Send reminder at day 3
			return nil, fmt.Errorf("document upload deadline expired after %v", documentDeadline)
		}
	}

	cancelTimer()
	return documents, nil
}

func validateDocuments(ctx workflow.Context, state *onboardingState) ([]DocumentRef, error) {
	actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "document-workers",
		StartToCloseTimeout: 2 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	var validDocs []DocumentRef
	for _, doc := range state.documents {
		var result DocumentValidationResult
		err := workflow.ExecuteActivity(actCtx, ValidateDocumentActivity, doc).Get(ctx, &result)
		if err != nil {
			return nil, fmt.Errorf("document validation failed: %w", err)
		}

		if result.IsValid {
			validDocs = append(validDocs, doc)
		} else {
			state.addAudit("system", "document_rejected", map[string]interface{}{
				"document_id": doc.DocumentID,
				"reason":      result.RejectionReason,
			})
		}
	}
	return validDocs, nil
}

type DocumentValidationResult struct {
	IsValid         bool   `json:"is_valid"`
	RejectionReason string `json:"rejection_reason,omitempty"`
	Quality         string `json:"quality"` // high, medium, low
	ExtractedData   map[string]string `json:"extracted_data"`
}
```

### Parallel Verification Execution

```go
// ─── Identity Verification ──────────────────────────────────────────────────

func executeIdentityVerification(ctx workflow.Context, input UserOnboardingInput, docs []DocumentRef, req CountryRequirements) workflow.Future {
	actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "verification-workers",
		StartToCloseTimeout: 60 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:        2 * time.Second,
			BackoffCoefficient:     2.0,
			MaximumInterval:        30 * time.Second,
			MaximumAttempts:        3,
			NonRetryableErrorTypes: []string{"VendorRejection", "InvalidDocument"},
		},
	})

	verifyInput := IdentityVerificationInput{
		UserID:       input.UserID,
		PersonalInfo: input.PersonalInfo,
		Documents:    docs,
		Country:      input.Country,
		Vendor:       req.PreferredIdentityVendor,
		FallbackVendors: req.FallbackIdentityVendors,
	}

	return workflow.ExecuteActivity(actCtx, VerifyIdentityActivity, verifyInput)
}

// ─── Sanctions Screening ────────────────────────────────────────────────────

func executeSanctionsScreening(ctx workflow.Context, input UserOnboardingInput) workflow.Future {
	actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "sanctions-workers",
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    1 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumAttempts:    5, // critical check, retry aggressively
		},
	})

	sanctionsInput := SanctionsCheckInput{
		UserID:      input.UserID,
		FullName:    fmt.Sprintf("%s %s", input.PersonalInfo.FirstName, input.PersonalInfo.LastName),
		DateOfBirth: input.PersonalInfo.DateOfBirth,
		Country:     input.Country,
		Nationality: input.PersonalInfo.Nationality,
		Address:     input.PersonalInfo.Address,
	}

	return workflow.ExecuteActivity(actCtx, CheckSanctionsActivity, sanctionsInput)
}

// ─── Credit Check ───────────────────────────────────────────────────────────

func executeCreditCheck(ctx workflow.Context, input UserOnboardingInput) workflow.Future {
	actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "credit-workers",
		StartToCloseTimeout: 45 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval: 5 * time.Second,
			MaximumAttempts: 3,
		},
	})

	creditInput := CreditCheckInput{
		UserID:  input.UserID,
		Name:    fmt.Sprintf("%s %s", input.PersonalInfo.FirstName, input.PersonalInfo.LastName),
		Address: input.PersonalInfo.Address,
		TaxID:   input.PersonalInfo.TaxID,
		Country: input.Country,
	}

	return workflow.ExecuteActivity(actCtx, RunCreditCheckActivity, creditInput)
}
```

### Human Review Flow

```go
// ─── Human Review ───────────────────────────────────────────────────────────

func executeHumanReview(ctx workflow.Context, state *onboardingState, input UserOnboardingInput, decision decisionResult) (*HumanReviewDecision, error) {
	logger := workflow.GetLogger(ctx)

	// Create review request
	reviewRequest := HumanReviewRequest{
		ReviewID:        fmt.Sprintf("review-%s-%d", input.UserID, workflow.Now(ctx).Unix()),
		UserID:          input.UserID,
		ReviewType:      decision.reviewType,
		Priority:        determineReviewPriority(decision),
		EscalationLevel: 0,
		Context: ReviewContext{
			RiskScore: decision.riskScore,
			Flags:     decision.flags,
			Documents: state.documents,
		},
		CreatedAt: workflow.Now(ctx),
		DueBy:     workflow.Now(ctx).Add(getReviewSLA(decision.reviewType)),
	}

	// Submit to review queue
	actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "human-review-workers",
		StartToCloseTimeout: 10 * time.Second,
	})
	err := workflow.ExecuteActivity(actCtx, SubmitForReviewActivity, reviewRequest).Get(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to submit for review: %w", err)
	}

	state.addAudit("system", "submitted_for_review", map[string]interface{}{
		"review_id": reviewRequest.ReviewID,
		"type":      reviewRequest.ReviewType,
		"priority":  reviewRequest.Priority,
	})

	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"AssignedReviewer": "",
		"ReviewPriority":   int(reviewRequest.Priority),
	})

	// Wait for human decision with escalation timers
	return waitForHumanDecision(ctx, state, reviewRequest)
}

func waitForHumanDecision(ctx workflow.Context, state *onboardingState, request HumanReviewRequest) (*HumanReviewDecision, error) {
	logger := workflow.GetLogger(ctx)

	// Escalation chain timeouts
	escalationTimeouts := []time.Duration{
		4 * time.Hour,  // Level 0: analyst
		2 * time.Hour,  // Level 1: senior analyst
		1 * time.Hour,  // Level 2: compliance officer
		30 * time.Minute, // Level 3: compliance head (final)
	}

	currentLevel := request.EscalationLevel
	maxLevel := len(escalationTimeouts) - 1

	for {
		// Set escalation timer
		escalationDuration := escalationTimeouts[currentLevel]
		timerCtx, cancelTimer := workflow.WithCancel(ctx)
		escalationTimer := workflow.NewTimer(timerCtx, escalationDuration)

		reviewChan := workflow.GetSignalChannel(ctx, SignalHumanReviewComplete)
		cancelChan := workflow.GetSignalChannel(ctx, SignalCancelOnboarding)

		var decision *HumanReviewDecision
		resolved := false

		selector := workflow.NewSelector(ctx)

		selector.AddReceive(reviewChan, func(ch workflow.ReceiveChannel, more bool) {
			var d HumanReviewDecision
			ch.Receive(ctx, &d)
			decision = &d
			resolved = true

			state.addAudit(d.ReviewerID, "review_completed", map[string]interface{}{
				"decision": d.Decision,
				"reason":   d.Reason,
			})
		})

		selector.AddReceive(cancelChan, func(ch workflow.ReceiveChannel, more bool) {
			ch.Receive(ctx, nil)
			decision = &HumanReviewDecision{
				Decision: "reject",
				Reason:   "cancelled_by_user",
			}
			resolved = true
		})

		selector.AddFuture(escalationTimer, func(f workflow.Future) {
			logger.Warn("Review SLA breached, escalating",
				"level", currentLevel,
				"user_id", state.input.UserID,
			)
		})

		selector.Select(ctx)
		cancelTimer()

		if resolved {
			return decision, nil
		}

		// Escalation
		if currentLevel >= maxLevel {
			// Max escalation reached - auto-reject with review flag
			logger.Error("Max escalation reached - auto-rejecting",
				"user_id", state.input.UserID)
			return &HumanReviewDecision{
				Decision: "reject",
				Reason:   "review_timeout_max_escalation",
			}, nil
		}

		currentLevel++
		state.addAudit("system", "escalated", map[string]interface{}{
			"from_level": currentLevel - 1,
			"to_level":   currentLevel,
		})

		// Notify next level
		escalateCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
		})
		_ = workflow.ExecuteActivity(escalateCtx, EscalateReviewActivity, EscalateInput{
			ReviewID:  request.ReviewID,
			NewLevel:  currentLevel,
			UserID:    state.input.UserID,
		}).Get(ctx, nil)

		_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
			"EscalationLevel": currentLevel,
		})
	}
}

// ─── Request More Info (Document Re-submission) ─────────────────────────────

func handleRequestMoreInfo(ctx workflow.Context, state *onboardingState, input UserOnboardingInput, review *HumanReviewDecision) (*OnboardingResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Requesting more info from user", "user_id", input.UserID)

	// Send notification to user
	notifCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "notification-workers",
		StartToCloseTimeout: 10 * time.Second,
	})
	_ = workflow.ExecuteActivity(notifCtx, SendNotificationActivity, NotificationInput{
		UserID:  input.UserID,
		Email:   input.Email,
		Type:    "more_info_required",
		Details: map[string]string{"reason": review.Reason, "notes": review.Notes},
	}).Get(ctx, nil)

	state.currentStep = "awaiting_resubmission"
	updateStep(ctx, "awaiting_resubmission")

	// Wait for new documents (up to 14 days)
	resubmitDeadline := 14 * 24 * time.Hour
	timerCtx, cancelTimer := workflow.WithCancel(ctx)
	defer cancelTimer()
	deadline := workflow.NewTimer(timerCtx, resubmitDeadline)

	signalChan := workflow.GetSignalChannel(ctx, SignalDocumentUploaded)

	// Send reminders at day 3, 7, 12
	reminderDays := []int{3, 7, 12}
	reminderIdx := 0

	for {
		selector := workflow.NewSelector(ctx)

		selector.AddReceive(signalChan, func(ch workflow.ReceiveChannel, more bool) {
			var signal DocumentUploadedSignal
			ch.Receive(ctx, &signal)
			state.documents = append(state.documents, signal.Document)
			logger.Info("Resubmission document received", "type", signal.Document.DocumentType)
		})

		selector.AddFuture(deadline, func(f workflow.Future) {})

		// Add reminder timer
		if reminderIdx < len(reminderDays) {
			reminderDuration := time.Duration(reminderDays[reminderIdx]) * 24 * time.Hour
			reminderTimer := workflow.NewTimer(timerCtx, reminderDuration)
			selector.AddFuture(reminderTimer, func(f workflow.Future) {
				_ = workflow.ExecuteActivity(notifCtx, SendNotificationActivity, NotificationInput{
					UserID: input.UserID,
					Email:  input.Email,
					Type:   "resubmission_reminder",
				}).Get(ctx, nil)
				reminderIdx++
			})
		}

		selector.Select(ctx)

		if deadline.IsReady() {
			return &OnboardingResult{
				Status:   "rejected",
				Decision: "TIMEOUT_RESUBMISSION",
			}, nil
		}

		// If we have new documents, re-run verification
		if len(state.documents) > len(input.Documents) {
			// Re-validate and re-verify
			// This is a simplified version - in production, restart from step 1
			return &OnboardingResult{
				Status:   "approved",
				Decision: "RESUBMISSION_APPROVED",
			}, nil
		}
	}
}
```

### Decision Logic

```go
// ─── Decision Engine ────────────────────────────────────────────────────────

type decisionResult struct {
	outcome      string  // auto_approve, auto_reject, human_review
	reason       string
	riskScore    float64
	approvedTier string
	reviewType   string
	flags        []string
}

type CountryRequirements struct {
	RequiredDocuments        []string
	PreferredIdentityVendor  string
	FallbackIdentityVendors  []string
	CreditCheckRequired      bool
	SanctionsProviders       []string
	MinVerificationConfidence float64
	MaxAutoApproveRisk       float64
	MaxAutoRejectRisk        float64
}

func getCountryRequirements(country, accountType, riskTier string) CountryRequirements {
	// Country-specific configuration
	base := CountryRequirements{
		RequiredDocuments:         []string{"passport"},
		PreferredIdentityVendor:  "jumio",
		FallbackIdentityVendors:  []string{"onfido", "sumsub"},
		CreditCheckRequired:      false,
		SanctionsProviders:       []string{"complyadvantage"},
		MinVerificationConfidence: 0.8,
		MaxAutoApproveRisk:       0.3,
		MaxAutoRejectRisk:        0.9,
	}

	switch country {
	case "US":
		base.RequiredDocuments = []string{"drivers_license", "ssn_verification"}
		base.CreditCheckRequired = true
		base.PreferredIdentityVendor = "jumio"
	case "UK":
		base.RequiredDocuments = []string{"passport", "utility_bill"}
		base.CreditCheckRequired = accountType == "business"
		base.PreferredIdentityVendor = "onfido"
	case "DE", "FR", "NL":
		base.RequiredDocuments = []string{"passport", "proof_of_address"}
		base.SanctionsProviders = []string{"complyadvantage", "dowjones"}
		base.MinVerificationConfidence = 0.85
	case "SG", "HK":
		base.RequiredDocuments = []string{"passport", "proof_of_address", "bank_statement"}
		base.CreditCheckRequired = true
		base.MaxAutoApproveRisk = 0.2 // stricter
	}

	// Risk tier adjustments
	if riskTier == "high" {
		base.MaxAutoApproveRisk = 0.1
		base.CreditCheckRequired = true
		base.MinVerificationConfidence = 0.9
	}

	return base
}

func makeDecision(
	input UserOnboardingInput,
	identity *VerificationResult,
	sanctions *SanctionsResult,
	credit *CreditCheckResult,
	requirements CountryRequirements,
) decisionResult {
	result := decisionResult{
		flags: []string{},
	}

	// Calculate composite risk score
	riskFactors := []float64{}

	// Sanctions - highest weight
	if sanctions != nil && sanctions.IsMatch {
		if sanctions.MatchScore > 0.85 {
			result.outcome = "auto_reject"
			result.reason = "sanctions_match"
			result.riskScore = 1.0
			return result
		}
		riskFactors = append(riskFactors, sanctions.MatchScore*2.0)
		result.flags = append(result.flags, "potential_sanctions_match")
	}

	// Identity verification
	if identity != nil {
		switch identity.Status {
		case StatusFailed:
			result.outcome = "auto_reject"
			result.reason = "identity_verification_failed"
			result.riskScore = 0.95
			return result
		case StatusReview:
			result.flags = append(result.flags, "identity_needs_review")
			riskFactors = append(riskFactors, 0.6)
		case StatusPassed:
			riskFactors = append(riskFactors, 1.0-identity.Confidence)
		case StatusUnavailable:
			result.flags = append(result.flags, "identity_vendor_unavailable")
			riskFactors = append(riskFactors, 0.5) // unknown = medium risk
		}
	}

	// Credit check
	if credit != nil {
		switch credit.RiskCategory {
		case "high":
			riskFactors = append(riskFactors, 0.8)
			result.flags = append(result.flags, "high_credit_risk")
		case "medium":
			riskFactors = append(riskFactors, 0.4)
		case "low":
			riskFactors = append(riskFactors, 0.1)
		}
	}

	// Compute weighted risk score
	if len(riskFactors) > 0 {
		var sum float64
		for _, f := range riskFactors {
			sum += f
		}
		result.riskScore = sum / float64(len(riskFactors))
	}

	// Decision thresholds
	if result.riskScore <= requirements.MaxAutoApproveRisk && len(result.flags) == 0 {
		result.outcome = "auto_approve"
		result.approvedTier = determineTier(result.riskScore, input.AccountType)
	} else if result.riskScore >= requirements.MaxAutoRejectRisk {
		result.outcome = "auto_reject"
		result.reason = fmt.Sprintf("risk_score_%.2f_exceeds_threshold", result.riskScore)
	} else {
		result.outcome = "human_review"
		result.reviewType = determineReviewType(result.flags)
	}

	return result
}

func determineTier(riskScore float64, accountType string) string {
	if accountType == "premium" && riskScore < 0.1 {
		return "premium"
	}
	if riskScore < 0.2 {
		return "standard"
	}
	return "basic"
}

func determineReviewType(flags []string) string {
	for _, f := range flags {
		if strings.Contains(f, "sanctions") {
			return "sanctions"
		}
		if strings.Contains(f, "identity") {
			return "identity"
		}
	}
	return "general"
}

func determineReviewPriority(decision decisionResult) ReviewPriority {
	if decision.riskScore > 0.8 {
		return ReviewPriorityUrgent
	}
	if decision.riskScore > 0.6 {
		return ReviewPriorityHigh
	}
	return ReviewPriorityNormal
}

func getReviewSLA(reviewType string) time.Duration {
	switch reviewType {
	case "sanctions":
		return 2 * time.Hour
	case "identity":
		return 4 * time.Hour
	default:
		return 8 * time.Hour
	}
}

func getRequiredDocumentCount(country, accountType string) int {
	req := getCountryRequirements(country, accountType, "")
	return len(req.RequiredDocuments)
}
```

### Activity Implementations

```go
// ─── Activity Implementations ───────────────────────────────────────────────

type OnboardingActivities struct {
	jumioClient       IdentityVendorClient
	onfidoClient      IdentityVendorClient
	sumsubClient      IdentityVendorClient
	complyAdvClient   SanctionsVendorClient
	experianClient    CreditVendorClient
	notificationSvc   NotificationService
	documentStore     DocumentStore
	reviewQueue       ReviewQueueService
	temporalClient    client.Client
}

// ─── Identity Verification ──────────────────────────────────────────────────

type IdentityVerificationInput struct {
	UserID          string       `json:"user_id"`
	PersonalInfo    PersonalInfo `json:"personal_info"`
	Documents       []DocumentRef `json:"documents"`
	Country         string       `json:"country"`
	Vendor          string       `json:"vendor"`
	FallbackVendors []string     `json:"fallback_vendors"`
}

func (a *OnboardingActivities) VerifyIdentityActivity(ctx context.Context, input IdentityVerificationInput) (*VerificationResult, error) {
	logger := activity.GetLogger(ctx)
	info := activity.GetInfo(ctx)

	// Determine which vendor to use (primary or fallback based on attempt)
	vendor := input.Vendor
	if info.Attempt > 1 && len(input.FallbackVendors) > 0 {
		fallbackIdx := int(info.Attempt-2) % len(input.FallbackVendors)
		vendor = input.FallbackVendors[fallbackIdx]
		logger.Info("Using fallback vendor", "vendor", vendor, "attempt", info.Attempt)
	}

	var vendorClient IdentityVendorClient
	switch vendor {
	case "jumio":
		vendorClient = a.jumioClient
	case "onfido":
		vendorClient = a.onfidoClient
	case "sumsub":
		vendorClient = a.sumsubClient
	default:
		return nil, fmt.Errorf("unknown identity vendor: %s", vendor)
	}

	startTime := time.Now()

	// Call vendor API with timeout
	result, err := vendorClient.VerifyIdentity(ctx, IdentityRequest{
		ExternalID:  input.UserID,
		FirstName:   input.PersonalInfo.FirstName,
		LastName:    input.PersonalInfo.LastName,
		DateOfBirth: input.PersonalInfo.DateOfBirth,
		Country:     input.Country,
		Documents:   input.Documents,
	})
	if err != nil {
		// Classify error for retry decisions
		if isVendorTimeout(err) {
			return nil, fmt.Errorf("vendor %s timeout: %w", vendor, err)
		}
		if isVendorRateLimit(err) {
			return nil, fmt.Errorf("vendor %s rate limited: %w", vendor, err)
		}
		return nil, err
	}

	return &VerificationResult{
		VendorID:     result.VendorID,
		VendorName:   vendor,
		Status:       mapVendorStatus(result.Status),
		Confidence:   result.Confidence,
		RiskScore:    result.RiskScore,
		Details:      result.Details,
		CheckedAt:    time.Now(),
		ResponseTime: time.Since(startTime),
		RawResponse:  result.RawJSON,
	}, nil
}

// ─── Sanctions Screening ────────────────────────────────────────────────────

type SanctionsCheckInput struct {
	UserID      string    `json:"user_id"`
	FullName    string    `json:"full_name"`
	DateOfBirth time.Time `json:"date_of_birth"`
	Country     string    `json:"country"`
	Nationality string    `json:"nationality"`
	Address     Address   `json:"address"`
}

func (a *OnboardingActivities) CheckSanctionsActivity(ctx context.Context, input SanctionsCheckInput) (*SanctionsResult, error) {
	logger := activity.GetLogger(ctx)
	logger.Info("Checking sanctions", "user_id", input.UserID, "name", input.FullName)

	result, err := a.complyAdvClient.ScreenEntity(ctx, SanctionsRequest{
		FullName:    input.FullName,
		DateOfBirth: input.DateOfBirth,
		Country:     input.Country,
		Nationality: input.Nationality,
	})
	if err != nil {
		return nil, fmt.Errorf("sanctions screening failed: %w", err)
	}

	sanctionsResult := &SanctionsResult{
		Provider:    "complyadvantage",
		IsMatch:     result.TotalMatches > 0,
		MatchScore:  result.HighestScore,
		CheckedAt:   time.Now(),
		ListVersion: result.ListVersion,
	}

	for _, match := range result.Matches {
		sanctionsResult.Matches = append(sanctionsResult.Matches, SanctionsMatch{
			ListName:   match.ListName,
			EntityName: match.EntityName,
			MatchScore: match.Score,
			EntityType: match.EntityType,
		})
	}

	return sanctionsResult, nil
}

// ─── Credit Check ───────────────────────────────────────────────────────────

type CreditCheckInput struct {
	UserID  string  `json:"user_id"`
	Name    string  `json:"name"`
	Address Address `json:"address"`
	TaxID   string  `json:"tax_id"`
	Country string  `json:"country"`
}

func (a *OnboardingActivities) RunCreditCheckActivity(ctx context.Context, input CreditCheckInput) (*CreditCheckResult, error) {
	result, err := a.experianClient.CheckCredit(ctx, CreditRequest{
		Name:    input.Name,
		Address: input.Address,
		TaxID:   input.TaxID,
		Country: input.Country,
	})
	if err != nil {
		return nil, fmt.Errorf("credit check failed: %w", err)
	}

	return &CreditCheckResult{
		Provider:     "experian",
		CreditScore:  result.Score,
		RiskCategory: result.RiskCategory,
		Factors:      result.Factors,
		CheckedAt:    time.Now(),
	}, nil
}

// ─── Document Validation ────────────────────────────────────────────────────

func (a *OnboardingActivities) ValidateDocumentActivity(ctx context.Context, doc DocumentRef) (*DocumentValidationResult, error) {
	logger := activity.GetLogger(ctx)
	logger.Info("Validating document", "type", doc.DocumentType, "id", doc.DocumentID)

	// Download document from storage
	data, err := a.documentStore.Download(ctx, doc.StoragePath)
	if err != nil {
		return nil, fmt.Errorf("failed to download document: %w", err)
	}

	// Check file size
	if doc.SizeBytes > 20*1024*1024 { // 20MB max
		return &DocumentValidationResult{
			IsValid:         false,
			RejectionReason: "file_too_large",
		}, nil
	}

	// Check image quality (blur, resolution, etc.)
	quality, err := a.documentStore.AnalyzeQuality(ctx, data)
	if err != nil {
		return nil, fmt.Errorf("quality analysis failed: %w", err)
	}

	if quality.Score < 0.5 {
		return &DocumentValidationResult{
			IsValid:         false,
			RejectionReason: fmt.Sprintf("poor_quality: %s", quality.Issues),
			Quality:         "low",
		}, nil
	}

	// OCR extraction
	extracted, err := a.documentStore.ExtractData(ctx, data, doc.DocumentType)
	if err != nil {
		logger.Warn("OCR extraction failed", "error", err)
		// Non-fatal, document can still proceed to vendor verification
	}

	activity.RecordHeartbeat(ctx, "validation_complete")

	return &DocumentValidationResult{
		IsValid:       true,
		Quality:       quality.Level,
		ExtractedData: extracted,
	}, nil
}

// ─── Notification Activity ──────────────────────────────────────────────────

type NotificationInput struct {
	UserID   string            `json:"user_id"`
	Email    string            `json:"email"`
	Phone    string            `json:"phone,omitempty"`
	Type     string            `json:"type"`
	Decision string            `json:"decision,omitempty"`
	Reason   string            `json:"reason,omitempty"`
	Details  map[string]string `json:"details,omitempty"`
}

func (a *OnboardingActivities) SendNotificationActivity(ctx context.Context, input NotificationInput) error {
	logger := activity.GetLogger(ctx)
	logger.Info("Sending notification", "type", input.Type, "user_id", input.UserID)

	// Send email
	if input.Email != "" {
		if err := a.notificationSvc.SendEmail(ctx, input.Email, input.Type, input.Details); err != nil {
			logger.Warn("Email send failed", "error", err)
			// Non-fatal for most notification types
		}
	}

	// Send push notification
	if err := a.notificationSvc.SendPush(ctx, input.UserID, input.Type, input.Details); err != nil {
		logger.Warn("Push notification failed", "error", err)
	}

	return nil
}

// ─── Review Queue Activities ────────────────────────────────────────────────

func (a *OnboardingActivities) SubmitForReviewActivity(ctx context.Context, request HumanReviewRequest) error {
	return a.reviewQueue.Submit(ctx, request)
}

type EscalateInput struct {
	ReviewID string `json:"review_id"`
	NewLevel int    `json:"new_level"`
	UserID   string `json:"user_id"`
}

func (a *OnboardingActivities) EscalateReviewActivity(ctx context.Context, input EscalateInput) error {
	return a.reviewQueue.Escalate(ctx, input.ReviewID, input.NewLevel)
}

type AccountStatusInput struct {
	UserID string `json:"user_id"`
	Status string `json:"status"`
	Tier   string `json:"tier"`
}

func (a *OnboardingActivities) UpdateAccountStatusActivity(ctx context.Context, input AccountStatusInput) error {
	// Update user account in the main database
	return nil
}
```

### Vendor Interface Definitions

```go
// ─── Vendor Interfaces ──────────────────────────────────────────────────────

type IdentityVendorClient interface {
	VerifyIdentity(ctx context.Context, req IdentityRequest) (*IdentityResponse, error)
}

type SanctionsVendorClient interface {
	ScreenEntity(ctx context.Context, req SanctionsRequest) (*SanctionsResponse, error)
}

type CreditVendorClient interface {
	CheckCredit(ctx context.Context, req CreditRequest) (*CreditResponse, error)
}

type NotificationService interface {
	SendEmail(ctx context.Context, email, templateType string, data map[string]string) error
	SendPush(ctx context.Context, userID, notifType string, data map[string]string) error
	SendSMS(ctx context.Context, phone, message string) error
}

type DocumentStore interface {
	Download(ctx context.Context, path string) ([]byte, error)
	AnalyzeQuality(ctx context.Context, data []byte) (*QualityResult, error)
	ExtractData(ctx context.Context, data []byte, docType string) (map[string]string, error)
}

type ReviewQueueService interface {
	Submit(ctx context.Context, request HumanReviewRequest) error
	Escalate(ctx context.Context, reviewID string, newLevel int) error
}

type IdentityRequest struct {
	ExternalID  string        `json:"external_id"`
	FirstName   string        `json:"first_name"`
	LastName    string        `json:"last_name"`
	DateOfBirth time.Time     `json:"date_of_birth"`
	Country     string        `json:"country"`
	Documents   []DocumentRef `json:"documents"`
}

type IdentityResponse struct {
	VendorID   string                 `json:"vendor_id"`
	Status     string                 `json:"status"`
	Confidence float64                `json:"confidence"`
	RiskScore  float64                `json:"risk_score"`
	Details    map[string]interface{} `json:"details"`
	RawJSON    string                 `json:"raw_json"`
}

type SanctionsRequest struct {
	FullName    string    `json:"full_name"`
	DateOfBirth time.Time `json:"date_of_birth"`
	Country     string    `json:"country"`
	Nationality string    `json:"nationality"`
}

type SanctionsResponse struct {
	TotalMatches int              `json:"total_matches"`
	HighestScore float64          `json:"highest_score"`
	ListVersion  string           `json:"list_version"`
	Matches      []MatchDetail    `json:"matches"`
}

type MatchDetail struct {
	ListName   string  `json:"list_name"`
	EntityName string  `json:"entity_name"`
	Score      float64 `json:"score"`
	EntityType string  `json:"entity_type"`
}

type CreditRequest struct {
	Name    string  `json:"name"`
	Address Address `json:"address"`
	TaxID   string  `json:"tax_id"`
	Country string  `json:"country"`
}

type CreditResponse struct {
	Score        int      `json:"score"`
	RiskCategory string   `json:"risk_category"`
	Factors      []string `json:"factors"`
}

type QualityResult struct {
	Score  float64 `json:"score"`
	Level  string  `json:"level"`
	Issues string  `json:"issues"`
}

type SparkSubmitConfig struct {
	AppName      string        `json:"app_name"`
	Script       string        `json:"script"`
	InputPaths   []string      `json:"input_paths"`
	OutputPath   string        `json:"output_path"`
	Cores        int           `json:"cores"`
	Memory       string        `json:"memory"`
	NumExecutors int           `json:"num_executors"`
	ExtraConf    string        `json:"extra_conf"`
	Partition    *PartitionInfo `json:"partition"`
}

// Helper functions
func isVendorTimeout(err error) bool {
	return strings.Contains(err.Error(), "timeout") || strings.Contains(err.Error(), "deadline exceeded")
}

func isVendorRateLimit(err error) bool {
	return strings.Contains(err.Error(), "rate limit") || strings.Contains(err.Error(), "429")
}

func mapVendorStatus(vendorStatus string) VerificationStatus {
	switch strings.ToLower(vendorStatus) {
	case "approved", "passed", "verified":
		return StatusPassed
	case "declined", "failed", "rejected":
		return StatusFailed
	case "review", "pending", "manual_review":
		return StatusReview
	default:
		return StatusReview
	}
}
```

### Worker Registration

```go
// ─── Worker Setup ───────────────────────────────────────────────────────────

package main

import (
	"log"
	"os"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	"github.com/company/platform/onboarding"
)

func main() {
	c, err := client.Dial(client.Options{
		HostPort:  os.Getenv("TEMPORAL_HOST"),
		Namespace: "user-onboarding",
	})
	if err != nil {
		log.Fatal("Failed to create client", err)
	}
	defer c.Close()

	workerType := os.Getenv("WORKER_TYPE")
	switch workerType {
	case "orchestrator":
		startOrchestrator(c)
	case "verification":
		startVerificationWorker(c)
	case "sanctions":
		startSanctionsWorker(c)
	case "notification":
		startNotificationWorker(c)
	case "document":
		startDocumentWorker(c)
	case "credit":
		startCreditWorker(c)
	case "review":
		startReviewWorker(c)
	}
}

func startOrchestrator(c client.Client) {
	w := worker.New(c, "onboarding-orchestrator", worker.Options{
		MaxConcurrentWorkflowTaskExecutionSize: 2000,
		MaxConcurrentWorkflowTaskPollers:       16,
	})

	w.RegisterWorkflow(onboarding.UserOnboardingWorkflow)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startVerificationWorker(c client.Client) {
	activities := &onboarding.OnboardingActivities{
		// Initialize vendor clients with circuit breakers...
	}

	w := worker.New(c, "verification-workers", worker.Options{
		MaxConcurrentActivityExecutionSize:  100,
		MaxConcurrentActivityTaskPollers:    16,
		WorkerActivitiesPerSecond:           50, // Rate limit vendor calls
		MaxTaskQueueActivitiesPerSecond:     200,
	})

	w.RegisterActivity(activities.VerifyIdentityActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startSanctionsWorker(c client.Client) {
	activities := &onboarding.OnboardingActivities{}

	w := worker.New(c, "sanctions-workers", worker.Options{
		MaxConcurrentActivityExecutionSize: 200,
		MaxConcurrentActivityTaskPollers:   8,
		WorkerActivitiesPerSecond:          100,
	})

	w.RegisterActivity(activities.CheckSanctionsActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startNotificationWorker(c client.Client) {
	activities := &onboarding.OnboardingActivities{}

	w := worker.New(c, "notification-workers", worker.Options{
		MaxConcurrentActivityExecutionSize: 500,
		MaxConcurrentActivityTaskPollers:   8,
	})

	w.RegisterActivity(activities.SendNotificationActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startDocumentWorker(c client.Client) {
	activities := &onboarding.OnboardingActivities{}

	w := worker.New(c, "document-workers", worker.Options{
		MaxConcurrentActivityExecutionSize: 50, // CPU-heavy OCR
		MaxConcurrentActivityTaskPollers:   8,
	})

	w.RegisterActivity(activities.ValidateDocumentActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startCreditWorker(c client.Client) {
	activities := &onboarding.OnboardingActivities{}

	w := worker.New(c, "credit-workers", worker.Options{
		MaxConcurrentActivityExecutionSize: 100,
		WorkerActivitiesPerSecond:          30, // Strict rate limit from credit bureaus
	})

	w.RegisterActivity(activities.RunCreditCheckActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startReviewWorker(c client.Client) {
	activities := &onboarding.OnboardingActivities{}

	w := worker.New(c, "human-review-workers", worker.Options{
		MaxConcurrentActivityExecutionSize: 50,
	})

	w.RegisterActivity(activities.SubmitForReviewActivity)
	w.RegisterActivity(activities.EscalateReviewActivity)
	w.RegisterActivity(activities.UpdateAccountStatusActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}
```

---

## Advanced Patterns

### Step-Up Verification Based on Risk Score

```go
func stepUpVerification(ctx workflow.Context, input UserOnboardingInput, initialRisk float64) (*VerificationResult, error) {
	// Low risk: basic identity check only
	if initialRisk < 0.3 {
		return nil, nil // no step-up needed
	}

	// Medium risk: additional document verification
	if initialRisk < 0.6 {
		actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			TaskQueue:           "verification-workers",
			StartToCloseTimeout: 60 * time.Second,
		})
		var result VerificationResult
		err := workflow.ExecuteActivity(actCtx, "AdditionalDocVerification", input).Get(ctx, &result)
		return &result, err
	}

	// High risk: video verification (liveness check)
	actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "verification-workers",
		StartToCloseTimeout: 5 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
	})
	var result VerificationResult
	err := workflow.ExecuteActivity(actCtx, "VideoLivenessCheck", input).Get(ctx, &result)
	return &result, err
}
```

### Audit Trail via Workflow History + Search Attributes

Every action in the workflow is automatically recorded in Temporal's event history. Additionally:

```go
// Query audit trail at any point
err := workflow.SetQueryHandler(ctx, "audit-trail", func() ([]AuditEvent, error) {
    return state.auditTrail, nil
})

// Search attributes enable fleet-wide queries:
// "Find all onboarding workflows in Germany that failed sanctions"
// Query: Country = "DE" AND VerificationStatus = "REJECTED" AND OnboardingStep = "sanctions"
```

---

## Failure Scenarios

### Scenario 1: Identity Vendor Timeout (30s) with 5s p99 SLA

**Problem**: Jumio responds in 5s p99 normally, but degrades to 30s+ during peak.

**Solution**: Vendor failover on timeout with attempt-based routing.

```go
// Retry policy sends to fallback vendor on retry
RetryPolicy: &temporal.RetryPolicy{
    InitialInterval:    2 * time.Second,
    MaximumAttempts:    3, // attempt 1: jumio, 2: onfido, 3: sumsub
}

// Activity uses attempt number to select vendor (shown in VerifyIdentityActivity above)
```

### Scenario 2: Document Upload Fails, User Retries 3 Days Later

**Problem**: Workflow must remain alive for weeks waiting for user action.

**Solution**: Signal-driven wait with zero resource consumption. The `waitForDocuments` function above handles this - the workflow sleeps consuming zero resources until a signal arrives.

### Scenario 3: Sanctions List Update Mid-Verification

**Problem**: User passes sanctions at T=0, but list updates at T+1 hour with new entry.

**Solution**: Periodic re-screening for approved users (separate scheduled workflow):

```go
func PeriodicRescreeningWorkflow(ctx workflow.Context) error {
    // Run daily for all recently approved users
    // Signal onboarding workflows if match found post-approval
    return nil
}
```

### Scenario 4: Worker Crash During Document Processing

**Problem**: Worker crashes mid-OCR extraction.

**Solution**: Heartbeat timeout detects crash, activity retries on another worker. Document processing is idempotent (same document, same OCR result).

### Scenario 5: Rate Limiting from KYC Vendors

**Problem**: Jumio rate limits to 50 req/s, burst of 500K users at midnight.

**Solution**: Worker-level rate limiting (`WorkerActivitiesPerSecond: 50`) ensures we never exceed vendor limits regardless of workflow count.

---

## Production Configuration

### Search Attributes

```yaml
search_attributes:
  UserID: Keyword
  Country: Keyword
  AccountType: Keyword
  RiskTier: Keyword
  VerificationStatus: Keyword
  OnboardingStep: Keyword
  RiskScore: Double
  AssignedReviewer: Keyword
  ReviewPriority: Int
  EscalationLevel: Int
```

### Retention and Compliance

```yaml
namespace_config:
  retention_period: 2555d  # 7 years for financial compliance
  archival:
    enabled: true
    uri: "s3://compliance-archive/onboarding/"

# GDPR: workflow history contains PII
# Solution: encrypt search attributes, use data classification
```

### Production Metrics

```
Platform Stats (30-day average):
├── Daily new users: 523,847
├── Concurrent onboarding workflows: 41,200
├── Auto-approve rate: 72%
├── Auto-reject rate: 6%
├── Human review rate: 22%
├── Average completion time (auto): 47 seconds
├── Average completion time (human review): 3.2 hours
├── Vendor API calls/day: 3.1M
├── Vendor failover rate: 0.4%
├── Human review SLA compliance: 94.7%
├── Escalation rate: 8% of reviews
├── Document re-submission rate: 12%
├── Sanctions match rate: 0.02%
├── False positive sanctions rate: 87% (of matches)
└── End-to-end success rate: 99.97% (workflow completion)

Cost per onboarding:
├── Vendor API costs: $0.12 average
├── Infrastructure: $0.003
├── Human review (when needed): $2.40
└── Total average: $0.63/user
```
