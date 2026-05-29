# Expense Management System

## 1. Functional Requirements

### Core Features
- **Receipt Capture & OCR**: Mobile photo capture, email forwarding, PDF upload with automatic text extraction
- **Expense Categorization**: ML-based auto-categorization with manual override
- **Policy Enforcement**: Real-time rule evaluation (auto-approve, flag, reject)
- **Approval Workflows**: Multi-level configurable approval chains
- **Corporate Card Integration**: Real-time transaction feed, auto-matching with receipts
- **Reimbursement Processing**: Batch payouts via ACH/wire, status tracking
- **Per-Diem Rules**: Location-based daily allowances (GSA rates)
- **Mileage Calculation**: GPS tracking or manual entry with IRS rate application
- **Reporting & Analytics**: Spend dashboards, budget vs actual, trend analysis
- **ERP Integration**: Sync with SAP, NetSuite, QuickBooks (GL codes, cost centers)

### User Flows
1. Employee submits expense → OCR extracts fields → Policy check → Route to approver
2. Corporate card transaction → Auto-match receipt → Policy check → Auto-approve if within policy
3. Finance admin configures policy rules → System enforces in real-time
4. Month-end: Generate reports → Export to ERP → Process reimbursements

## 2. Non-Functional Requirements

| Metric | Target |
|--------|--------|
| OCR Processing Time | < 5 seconds per receipt |
| Policy Evaluation | < 100ms per expense |
| API Latency (p99) | < 200ms |
| Availability | 99.9% |
| Throughput | 10K expenses/minute peak |
| Data Retention | 7 years (tax compliance) |
| OCR Accuracy | > 95% field extraction |
| Concurrent Users | 100K during month-end |

## 3. Capacity Estimation

### Assumptions
- 500K employees across all tenants
- Average 20 expenses/employee/month = 10M expenses/month
- Average receipt image: 2MB
- Metadata per expense: ~5KB

### Storage
- Receipt images: 10M × 2MB = 20TB/month → 240TB/year
- Metadata: 10M × 5KB = 50GB/month
- Audit logs: ~100GB/month
- Total: ~250TB/year (images dominate)

### Compute
- OCR processing: 10M/month ÷ 30 days ÷ 24h ÷ 3600s ≈ 4 receipts/sec average, 40/sec peak
- Policy evaluation: 10M/month + real-time card transactions ≈ 100 evaluations/sec peak
- API requests: 500K users × 5 requests/day = 2.5M/day ≈ 30 req/sec average, 300/sec peak

### Bandwidth
- Image uploads: 40/sec × 2MB = 80MB/sec peak inbound
- API responses: 300/sec × 10KB = 3MB/sec

## 4. Data Modeling

### Full Database Schemas

```sql
-- Core expense table
CREATE TABLE expenses (
    expense_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    employee_id UUID NOT NULL,
    report_id UUID REFERENCES expense_reports(report_id),
    category_id UUID REFERENCES categories(category_id),
    merchant_name VARCHAR(255),
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    transaction_date DATE NOT NULL,
    submission_date TIMESTAMP NOT NULL DEFAULT NOW(),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    -- DRAFT, SUBMITTED, APPROVED, REJECTED, REIMBURSED, FLAGGED
    policy_result JSONB, -- {compliant: bool, violations: [...]}
    card_transaction_id UUID REFERENCES card_transactions(transaction_id),
    cost_center VARCHAR(50),
    project_code VARCHAR(50),
    gl_code VARCHAR(20),
    receipt_ids UUID[],
    mileage_km DECIMAL(8, 2),
    per_diem_location VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT valid_status CHECK (status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED','REIMBURSED','FLAGGED'))
);

CREATE INDEX idx_expenses_tenant_employee ON expenses(tenant_id, employee_id);
CREATE INDEX idx_expenses_status ON expenses(tenant_id, status);
CREATE INDEX idx_expenses_report ON expenses(report_id);
CREATE INDEX idx_expenses_date ON expenses(tenant_id, transaction_date);
CREATE INDEX idx_expenses_card_txn ON expenses(card_transaction_id);

-- Expense reports (grouping)
CREATE TABLE expense_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    employee_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    total_amount DECIMAL(12, 2) DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'USD',
    submitted_at TIMESTAMP,
    approved_at TIMESTAMP,
    current_approver_id UUID,
    approval_level INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reports_approver ON expense_reports(current_approver_id, status);

-- Receipt storage
CREATE TABLE receipts (
    receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    expense_id UUID REFERENCES expenses(expense_id),
    storage_url TEXT NOT NULL,
    thumbnail_url TEXT,
    file_type VARCHAR(10), -- jpg, png, pdf
    file_size_bytes BIGINT,
    ocr_status VARCHAR(20) DEFAULT 'PENDING',
    ocr_result JSONB,
    ocr_confidence DECIMAL(3, 2),
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_receipts_expense ON receipts(expense_id);
CREATE INDEX idx_receipts_ocr_status ON receipts(ocr_status);

-- OCR extracted fields
CREATE TABLE ocr_extractions (
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id UUID REFERENCES receipts(receipt_id),
    merchant_name VARCHAR(255),
    merchant_name_confidence DECIMAL(3, 2),
    total_amount DECIMAL(12, 2),
    amount_confidence DECIMAL(3, 2),
    tax_amount DECIMAL(12, 2),
    tax_confidence DECIMAL(3, 2),
    transaction_date DATE,
    date_confidence DECIMAL(3, 2),
    currency VARCHAR(3),
    line_items JSONB, -- [{description, qty, unit_price, total}]
    raw_text TEXT,
    processing_time_ms INT,
    model_version VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Policy rules
CREATE TABLE policy_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(30) NOT NULL, -- SPENDING_LIMIT, CATEGORY_RESTRICTION, APPROVAL_THRESHOLD
    priority INT DEFAULT 0,
    conditions JSONB NOT NULL, -- DSL conditions
    actions JSONB NOT NULL, -- {action: 'APPROVE'|'FLAG'|'REJECT', reason: '...'}
    applies_to JSONB, -- {roles: [], departments: [], levels: []}
    effective_from DATE,
    effective_to DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_policy_rules_tenant ON policy_rules(tenant_id, is_active);

-- Approval workflow definitions
CREATE TABLE approval_workflows (
    workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    workflow_name VARCHAR(255),
    conditions JSONB, -- when to trigger this workflow
    steps JSONB NOT NULL, -- [{level: 1, approver_type: 'MANAGER'|'ROLE'|'SPECIFIC', approver_id: ...}]
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Approval actions
CREATE TABLE approval_actions (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES expense_reports(report_id),
    approver_id UUID NOT NULL,
    approval_level INT NOT NULL,
    action VARCHAR(10) NOT NULL, -- APPROVE, REJECT, RETURN
    comments TEXT,
    acted_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_approvals_report ON approval_actions(report_id);

-- Corporate card transactions
CREATE TABLE card_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    card_id UUID NOT NULL,
    employee_id UUID NOT NULL,
    merchant_name VARCHAR(255),
    merchant_category_code VARCHAR(4),
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    transaction_date TIMESTAMP NOT NULL,
    posted_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, MATCHED, UNMATCHED
    matched_expense_id UUID,
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_card_txns_employee ON card_transactions(tenant_id, employee_id, status);
CREATE INDEX idx_card_txns_unmatched ON card_transactions(tenant_id, status) WHERE status = 'UNMATCHED';

-- Categories
CREATE TABLE categories (
    category_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    parent_category_id UUID REFERENCES categories(category_id),
    gl_code VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE
);

-- Reimbursements
CREATE TABLE reimbursements (
    reimbursement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    employee_id UUID NOT NULL,
    report_id UUID REFERENCES expense_reports(report_id),
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    payment_method VARCHAR(20), -- ACH, WIRE, CHECK
    bank_account_id UUID,
    status VARCHAR(20) DEFAULT 'PENDING',
    -- PENDING, PROCESSING, COMPLETED, FAILED
    batch_id UUID,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reimbursements_status ON reimbursements(status);
CREATE INDEX idx_reimbursements_batch ON reimbursements(batch_id);

-- Per-diem rates
CREATE TABLE per_diem_rates (
    rate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location VARCHAR(100) NOT NULL,
    country VARCHAR(2) NOT NULL,
    lodging_rate DECIMAL(8, 2),
    meals_rate DECIMAL(8, 2),
    incidentals_rate DECIMAL(8, 2),
    effective_date DATE NOT NULL,
    source VARCHAR(50), -- GSA, COMPANY_CUSTOM
    UNIQUE(location, effective_date)
);

-- Mileage logs
CREATE TABLE mileage_logs (
    mileage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expense_id UUID REFERENCES expenses(expense_id),
    start_location POINT,
    end_location POINT,
    distance_km DECIMAL(8, 2) NOT NULL,
    rate_per_km DECIMAL(5, 3) NOT NULL,
    calculated_amount DECIMAL(8, 2) NOT NULL,
    route_polyline TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXPENSE MANAGEMENT SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  Mobile  │  │   Web    │  │  Email   │  │Corporate │  │   ERP    │          │
│  │   App    │  │  Portal  │  │ Forward  │  │Card Feed │  │  Systems │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │              │              │              │              │                │
│       └──────────────┴──────────────┴──────────────┴──────────────┘                │
│                                     │                                              │
│                          ┌──────────▼──────────┐                                  │
│                          │    API Gateway       │                                  │
│                          │  (Rate Limit/Auth)   │                                  │
│                          └──────────┬──────────┘                                  │
│                                     │                                              │
│       ┌─────────────────────────────┼─────────────────────────────────┐           │
│       │                             │                                  │           │
│  ┌────▼────┐  ┌────────────┐  ┌────▼─────┐  ┌──────────┐  ┌────────┐│           │
│  │ Expense │  │  Receipt   │  │ Approval │  │  Policy  │  │Reimburse││           │
│  │ Service │  │  Service   │  │ Service  │  │  Engine  │  │ Service ││           │
│  └────┬────┘  └─────┬──────┘  └────┬─────┘  └────┬─────┘  └────┬───┘│           │
│       │              │              │              │              │    │           │
│       │         ┌────▼─────┐        │              │              │    │           │
│       │         │   OCR    │        │              │              │    │           │
│       │         │ Pipeline │        │              │              │    │           │
│       │         └────┬─────┘        │              │              │    │           │
│       │              │              │              │              │    │           │
│  ┌────▼──────────────▼──────────────▼──────────────▼──────────────▼──┐│           │
│  │                        Kafka Event Bus                             ││           │
│  │  [expense.created] [receipt.processed] [policy.evaluated]          ││           │
│  │  [approval.requested] [reimbursement.initiated]                    ││           │
│  └────┬───────────────────────────────────────────────────────────────┘│           │
│       │                                                                │           │
│  ┌────▼────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐      │           │
│  │  PostgreSQL │  │   S3/Blob │  │  Redis   │  │ Elasticsearch│      │           │
│  │  (Metadata) │  │ (Receipts)│  │ (Cache)  │  │  (Search)    │      │           │
│  └─────────────┘  └───────────┘  └──────────┘  └──────────────┘      │           │
│                                                                        │           │
│  ┌─────────────────────────────────────────────────────────────┐      │           │
│  │              ML Services                                     │      │           │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐      │      │           │
│  │  │ OCR Engine  │  │ Categorizer  │  │ Receipt Match │      │      │           │
│  │  │ (Tesseract/ │  │   (BERT)     │  │   (Fuzzy)     │      │      │           │
│  │  │  AWS Textract)│ └──────────────┘  └───────────────┘      │      │           │
│  │  └─────────────┘                                            │      │           │
│  └─────────────────────────────────────────────────────────────┘      │           │
└───────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Submit Expense
```http
POST /api/v1/expenses
Content-Type: application/json
Authorization: Bearer <token>

{
  "category_id": "cat-meals-001",
  "merchant_name": "Uber Eats",
  "amount": 45.99,
  "currency": "USD",
  "transaction_date": "2024-01-15",
  "description": "Team lunch during client meeting",
  "cost_center": "CC-ENGINEERING",
  "project_code": "PRJ-ATLAS",
  "receipt_ids": ["rcpt-uuid-123"]
}

Response 201:
{
  "expense_id": "exp-uuid-456",
  "status": "SUBMITTED",
  "policy_result": {
    "compliant": true,
    "auto_approved": false,
    "violations": [],
    "warnings": [{"rule": "meal_photo_required", "message": "Consider adding itemized receipt"}]
  },
  "approval_workflow": {
    "current_level": 1,
    "approver": {"id": "mgr-001", "name": "Jane Smith"},
    "estimated_approval": "2024-01-16T10:00:00Z"
  }
}
```

### Upload Receipt
```http
POST /api/v1/receipts/upload
Content-Type: multipart/form-data
Authorization: Bearer <token>

file: <binary image data>
expense_id: "exp-uuid-456" (optional, link later)

Response 202:
{
  "receipt_id": "rcpt-uuid-123",
  "status": "PROCESSING",
  "estimated_completion_seconds": 5
}

-- Webhook callback after OCR:
POST <callback_url>
{
  "receipt_id": "rcpt-uuid-123",
  "ocr_status": "COMPLETED",
  "extracted_fields": {
    "merchant_name": {"value": "Uber Eats", "confidence": 0.97},
    "total_amount": {"value": 45.99, "confidence": 0.99},
    "tax_amount": {"value": 3.45, "confidence": 0.92},
    "transaction_date": {"value": "2024-01-15", "confidence": 0.95},
    "line_items": [
      {"description": "Caesar Salad", "amount": 14.99},
      {"description": "Burger Combo", "amount": 18.99},
      {"description": "Drinks x2", "amount": 8.56}
    ]
  }
}
```

### Evaluate Policy
```http
POST /api/v1/policy/evaluate
Content-Type: application/json

{
  "expense": {
    "amount": 450.00,
    "category": "TRAVEL_FLIGHTS",
    "employee_role": "IC3",
    "department": "Engineering",
    "project": "PRJ-ATLAS"
  }
}

Response 200:
{
  "decision": "FLAG",
  "triggered_rules": [
    {
      "rule_id": "rule-flight-limit",
      "rule_name": "Flight booking over $400 requires VP approval",
      "action": "FLAG",
      "threshold": 400.00,
      "actual": 450.00
    }
  ],
  "required_approval_level": 3,
  "auto_approve_eligible": false
}
```

### Approve/Reject Expense Report
```http
POST /api/v1/reports/{report_id}/approve
Authorization: Bearer <approver_token>

{
  "action": "APPROVE",
  "comments": "Approved - valid client meeting expense",
  "conditions": []
}

Response 200:
{
  "report_id": "rpt-uuid-789",
  "new_status": "APPROVED",
  "next_step": "REIMBURSEMENT_QUEUED",
  "reimbursement_eta": "2024-01-20"
}
```

### Get Expense Analytics
```http
GET /api/v1/analytics/spend?period=2024-Q1&group_by=category,department
Authorization: Bearer <admin_token>

Response 200:
{
  "period": "2024-Q1",
  "total_spend": 2450000.00,
  "budget_utilization": 0.78,
  "by_category": [
    {"category": "TRAVEL", "amount": 890000, "pct": 36.3, "trend": "+5%"},
    {"category": "MEALS", "amount": 450000, "pct": 18.4, "trend": "-2%"}
  ],
  "policy_violations": {"total": 234, "auto_resolved": 180, "pending": 54},
  "avg_reimbursement_time_days": 3.2
}
```

## 7. Deep Dives

### Deep Dive 1: OCR Pipeline

```
Receipt Image → Preprocessing → Text Extraction → Field Parsing → Confidence Scoring
```

#### Image Preprocessing
```python
import cv2
import numpy as np

class ReceiptPreprocessor:
    def preprocess(self, image_bytes: bytes) -> np.ndarray:
        # Decode image
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        # Step 1: Deskew
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        angle = self._detect_skew(gray)
        if abs(angle) > 0.5:
            img = self._rotate(img, angle)
        
        # Step 2: Perspective correction (detect receipt edges)
        contour = self._find_receipt_contour(gray)
        if contour is not None:
            img = self._four_point_transform(img, contour)
        
        # Step 3: Enhance contrast (adaptive thresholding)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Step 4: Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
        
        # Step 5: Resize to optimal DPI (300 DPI for OCR)
        scale = max(1.0, 2000 / max(denoised.shape))
        resized = cv2.resize(denoised, None, fx=scale, fy=scale)
        
        return resized
    
    def _detect_skew(self, gray: np.ndarray) -> float:
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100)
        if lines is None:
            return 0.0
        angles = [np.degrees(np.arctan2(y2-y1, x2-x1)) for [[x1,y1,x2,y2]] in lines]
        return np.median(angles)
```

#### Field Extraction & Parsing
```python
import re
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ExtractionResult:
    merchant_name: Optional[str] = None
    merchant_confidence: float = 0.0
    total_amount: Optional[float] = None
    amount_confidence: float = 0.0
    tax_amount: Optional[float] = None
    tax_confidence: float = 0.0
    transaction_date: Optional[str] = None
    date_confidence: float = 0.0
    line_items: List[dict] = None

class ReceiptFieldParser:
    # Amount patterns (handles $, €, £, commas, decimals)
    AMOUNT_PATTERNS = [
        r'(?:TOTAL|AMOUNT|DUE|BALANCE)[:\s]*[\$€£]?\s*(\d{1,6}[.,]\d{2})',
        r'[\$€£]\s*(\d{1,6}[.,]\d{2})\s*$',
        r'(\d{1,6}[.,]\d{2})\s*(?:USD|EUR|GBP)',
    ]
    
    # Date patterns
    DATE_PATTERNS = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\w{3}\s+\d{1,2},?\s+\d{4})',
        r'(\d{4}-\d{2}-\d{2})',
    ]
    
    # Tax patterns
    TAX_PATTERNS = [
        r'(?:TAX|GST|VAT|HST)[:\s]*[\$€£]?\s*(\d{1,4}[.,]\d{2})',
        r'(?:TAX|GST|VAT|HST)\s*\(?(\d{1,2}\.?\d?)%\)?\s*[\$€£]?\s*(\d{1,4}[.,]\d{2})',
    ]
    
    def parse(self, ocr_text: str, raw_blocks: list) -> ExtractionResult:
        result = ExtractionResult(line_items=[])
        
        # Merchant: Usually first 1-3 lines (largest font / top position)
        lines = ocr_text.strip().split('\n')
        result.merchant_name = self._extract_merchant(lines[:5], raw_blocks)
        result.merchant_confidence = self._score_merchant_confidence(result.merchant_name, raw_blocks)
        
        # Total amount: Scan bottom-up for TOTAL keyword
        result.total_amount = self._extract_amount(ocr_text)
        result.amount_confidence = self._score_amount_confidence(ocr_text, result.total_amount)
        
        # Date
        result.transaction_date = self._extract_date(ocr_text)
        result.date_confidence = 0.90 if result.transaction_date else 0.0
        
        # Tax
        result.tax_amount = self._extract_tax(ocr_text)
        result.tax_confidence = 0.85 if result.tax_amount else 0.0
        
        # Line items
        result.line_items = self._extract_line_items(lines)
        
        return result
    
    def _extract_merchant(self, top_lines: list, blocks: list) -> Optional[str]:
        # Heuristic: First non-numeric, non-address line with large font
        for line in top_lines:
            cleaned = line.strip()
            if len(cleaned) > 2 and not re.match(r'^[\d\s\-\(\)]+$', cleaned):
                if not re.match(r'^\d+\s+\w+\s+(St|Ave|Blvd|Rd|Dr)', cleaned):
                    return cleaned
        return None
    
    def _extract_amount(self, text: str) -> Optional[float]:
        # Prioritize "TOTAL" over "SUBTOTAL"
        for pattern in self.AMOUNT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                amount_str = matches[-1].replace(',', '')  # Take last match (final total)
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None
    
    def _score_amount_confidence(self, text: str, amount: Optional[float]) -> float:
        if amount is None:
            return 0.0
        # Higher confidence if TOTAL keyword is nearby
        if re.search(r'TOTAL.*' + re.escape(f"{amount:.2f}"), text, re.IGNORECASE):
            return 0.97
        return 0.80
```

#### Confidence Scoring & Human-in-the-Loop
```python
class ConfidenceRouter:
    THRESHOLDS = {
        'auto_accept': 0.92,
        'review_suggested': 0.75,
        'manual_required': 0.50,
    }
    
    def route(self, extraction: ExtractionResult) -> dict:
        avg_confidence = np.mean([
            extraction.amount_confidence,
            extraction.merchant_confidence,
            extraction.date_confidence,
        ])
        
        if avg_confidence >= self.THRESHOLDS['auto_accept']:
            return {'action': 'AUTO_FILL', 'requires_review': False}
        elif avg_confidence >= self.THRESHOLDS['review_suggested']:
            return {'action': 'AUTO_FILL', 'requires_review': True, 
                    'low_confidence_fields': self._get_low_fields(extraction)}
        else:
            return {'action': 'MANUAL_ENTRY', 'requires_review': True,
                    'suggestions': self._format_suggestions(extraction)}
```

### Deep Dive 2: Policy Engine

#### Rule DSL (Domain Specific Language)
```json
{
  "rule_id": "rule-001",
  "name": "Meal limit by role",
  "version": 2,
  "conditions": {
    "ALL": [
      {"field": "category", "op": "IN", "value": ["MEALS", "ENTERTAINMENT"]},
      {"field": "employee.level", "op": "LTE", "value": "IC4"}
    ]
  },
  "constraints": [
    {
      "type": "AMOUNT_LIMIT",
      "limit": 75.00,
      "period": "PER_TRANSACTION",
      "currency": "USD"
    },
    {
      "type": "AMOUNT_LIMIT",
      "limit": 500.00,
      "period": "MONTHLY",
      "currency": "USD"
    }
  ],
  "action_on_violation": "FLAG",
  "escalation": {"approval_level": 2}
}
```

#### Policy Evaluation Engine
```python
from typing import List, Dict, Any
from dataclasses import dataclass
import operator

@dataclass
class PolicyViolation:
    rule_id: str
    rule_name: str
    violation_type: str
    limit: float
    actual: float
    action: str

class PolicyEngine:
    OPERATORS = {
        'EQ': operator.eq, 'NEQ': operator.ne,
        'GT': operator.gt, 'GTE': operator.ge,
        'LT': operator.lt, 'LTE': operator.le,
        'IN': lambda a, b: a in b,
        'NOT_IN': lambda a, b: a not in b,
        'CONTAINS': lambda a, b: b in a,
        'REGEX': lambda a, b: bool(re.match(b, str(a))),
    }
    
    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db = db_client
        self._rule_cache = {}
    
    async def evaluate(self, expense: dict, employee: dict, tenant_id: str) -> dict:
        rules = await self._get_active_rules(tenant_id)
        violations = []
        warnings = []
        
        context = {**expense, 'employee': employee}
        
        for rule in sorted(rules, key=lambda r: r['priority'], reverse=True):
            if self._matches_conditions(rule['conditions'], context):
                if self._matches_applies_to(rule.get('applies_to'), employee):
                    violation = await self._check_constraints(rule, expense, employee)
                    if violation:
                        violations.append(violation)
        
        # Determine final action (most severe wins)
        action = self._determine_action(violations)
        
        return {
            'compliant': len(violations) == 0,
            'decision': action,
            'violations': [v.__dict__ for v in violations],
            'warnings': warnings,
            'auto_approve_eligible': action == 'APPROVE' and expense['amount'] < 50,
        }
    
    def _matches_conditions(self, conditions: dict, context: dict) -> bool:
        if 'ALL' in conditions:
            return all(self._eval_condition(c, context) for c in conditions['ALL'])
        elif 'ANY' in conditions:
            return any(self._eval_condition(c, context) for c in conditions['ANY'])
        elif 'NOT' in conditions:
            return not self._matches_conditions(conditions['NOT'], context)
        else:
            return self._eval_condition(conditions, context)
    
    def _eval_condition(self, condition: dict, context: dict) -> bool:
        field_value = self._resolve_field(condition['field'], context)
        op_func = self.OPERATORS[condition['op']]
        return op_func(field_value, condition['value'])
    
    def _resolve_field(self, field_path: str, context: dict) -> Any:
        parts = field_path.split('.')
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
    
    async def _check_constraints(self, rule: dict, expense: dict, employee: dict) -> PolicyViolation:
        for constraint in rule.get('constraints', []):
            if constraint['type'] == 'AMOUNT_LIMIT':
                if constraint['period'] == 'PER_TRANSACTION':
                    if expense['amount'] > constraint['limit']:
                        return PolicyViolation(
                            rule_id=rule['rule_id'], rule_name=rule['rule_name'],
                            violation_type='OVER_LIMIT', limit=constraint['limit'],
                            actual=expense['amount'], action=rule['action_on_violation']
                        )
                elif constraint['period'] == 'MONTHLY':
                    monthly_total = await self._get_monthly_spend(
                        employee['id'], rule['conditions']
                    )
                    if monthly_total + expense['amount'] > constraint['limit']:
                        return PolicyViolation(
                            rule_id=rule['rule_id'], rule_name=rule['rule_name'],
                            violation_type='MONTHLY_LIMIT_EXCEEDED',
                            limit=constraint['limit'],
                            actual=monthly_total + expense['amount'],
                            action=rule['action_on_violation']
                        )
        return None
    
    async def _get_monthly_spend(self, employee_id: str, conditions: dict) -> float:
        # Check Redis cache first
        cache_key = f"monthly_spend:{employee_id}:{hash(str(conditions))}"
        cached = await self.redis.get(cache_key)
        if cached:
            return float(cached)
        
        # Query DB
        total = await self.db.fetch_val("""
            SELECT COALESCE(SUM(amount), 0) FROM expenses 
            WHERE employee_id = $1 
            AND transaction_date >= date_trunc('month', CURRENT_DATE)
            AND status NOT IN ('REJECTED', 'DRAFT')
        """, employee_id)
        
        await self.redis.setex(cache_key, 300, str(total))  # Cache 5 min
        return total
```

#### Real-Time POS Enforcement vs Post-Submission
```
┌─────────────────────────────────────────────────────┐
│         Real-Time (Card Transaction)                 │
│                                                      │
│  Card Swipe → Issuer Auth Request → Policy Engine   │
│       ↓              ↓                    ↓          │
│  200ms budget   Approve/Decline    MCC + Amount     │
│                                    check only        │
│  (Limited context: no receipt, no description)       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│         Post-Submission (Full Context)               │
│                                                      │
│  Expense Submit → Full Policy Eval → Workflow Route  │
│       ↓                  ↓                ↓          │
│  All fields         All rules          Approve/      │
│  + receipt          + history           Flag/Reject   │
│  + project          + budget                         │
└─────────────────────────────────────────────────────┘
```

## 8. Component Optimization

### Kafka Configuration
```yaml
# Expense events topic
expense-events:
  partitions: 24
  replication-factor: 3
  retention.ms: 604800000  # 7 days
  cleanup.policy: delete
  min.insync.replicas: 2
  partition-key: tenant_id + employee_id  # Co-locate employee expenses

# OCR processing topic (longer retention for retries)
ocr-processing:
  partitions: 12
  replication-factor: 3
  retention.ms: 259200000  # 3 days
  max.message.bytes: 10485760  # 10MB for image refs

# Consumer groups
expense-policy-evaluator:
  max.poll.records: 50
  session.timeout.ms: 30000
  auto.offset.reset: earliest
```

### Redis Configuration
```yaml
redis:
  cluster:
    nodes: 6 (3 master + 3 replica)
    max-memory: 32GB per node
  
  # Cache patterns
  policy-rules:
    key: "policy:{tenant_id}:rules"
    ttl: 300  # 5 min - rules change infrequently
    type: hash
  
  monthly-spend:
    key: "spend:{employee_id}:{year}-{month}:{category}"
    ttl: 60  # 1 min - balance accuracy
    type: string
  
  approval-status:
    key: "approval:{report_id}"
    ttl: 3600
    type: hash
  
  rate-limiting:
    key: "ratelimit:{tenant_id}:{endpoint}"
    type: sliding-window
    window: 60s
    max-requests: 100
```

### OCR Pipeline Optimization
```yaml
ocr-pipeline:
  # Auto-scaling based on queue depth
  autoscaler:
    min-replicas: 2
    max-replicas: 20
    target-queue-depth: 100
    scale-up-period: 30s
    scale-down-period: 300s
  
  # GPU allocation for ML models
  gpu-pool:
    instance-type: g4dn.xlarge
    spot-instances: true  # 70% cost saving
    fallback-to-on-demand: true
  
  # Processing priorities
  priority-queues:
    - name: real-time  # User waiting for result
      max-latency: 5s
      gpu-share: 60%
    - name: batch      # Email forwards, bulk uploads
      max-latency: 60s
      gpu-share: 40%
```

## 9. Observability

### Key Metrics
```yaml
metrics:
  # OCR Pipeline
  - name: ocr_processing_duration_seconds
    type: histogram
    labels: [model_version, receipt_type, outcome]
    buckets: [0.5, 1, 2, 5, 10, 30]
  
  - name: ocr_field_confidence_score
    type: histogram
    labels: [field_name, model_version]
    buckets: [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
  
  - name: ocr_extraction_accuracy
    type: gauge  # Computed from user corrections
    labels: [field_name]
  
  # Policy Engine
  - name: policy_evaluation_duration_ms
    type: histogram
    labels: [tenant_id, rule_count]
    buckets: [5, 10, 25, 50, 100, 250]
  
  - name: policy_violations_total
    type: counter
    labels: [tenant_id, rule_type, action]
  
  # Business Metrics
  - name: expense_submission_total
    type: counter
    labels: [tenant_id, category, channel]
  
  - name: reimbursement_processing_days
    type: histogram
    labels: [tenant_id, payment_method]
  
  - name: approval_turnaround_hours
    type: histogram
    labels: [tenant_id, approval_level]

alerts:
  - name: OCRLatencyHigh
    expr: histogram_quantile(0.95, ocr_processing_duration_seconds) > 10
    severity: warning
    
  - name: PolicyEngineTimeout
    expr: policy_evaluation_duration_ms{quantile="0.99"} > 200
    severity: critical
    
  - name: ReimbursementBacklog
    expr: sum(reimbursements{status="PENDING"}) > 1000
    severity: warning
```

### Distributed Tracing
```
TraceID: expense-submit-flow
├── [API Gateway] 5ms - Auth + rate limit
├── [Expense Service] 15ms - Validate + persist
├── [Receipt Service] 3200ms - OCR pipeline
│   ├── [Preprocessor] 200ms - Image enhancement
│   ├── [Textract API] 2500ms - Text extraction
│   └── [Field Parser] 500ms - Structured extraction
├── [Policy Engine] 45ms - Rule evaluation
│   ├── [Redis] 2ms - Cache lookup (monthly spend)
│   └── [Rule Eval] 43ms - 12 rules evaluated
├── [Approval Service] 20ms - Route to approver
└── [Notification] 50ms - Push + email to approver
```

## 10. Failure Modes & Considerations

### Failure Handling
| Failure | Impact | Mitigation |
|---------|--------|------------|
| OCR service down | Receipts queue up | Async processing, exponential backoff, manual entry fallback |
| Policy engine timeout | Expenses stuck | Default-allow with post-hoc review flag |
| Card feed delay | Unmatched expenses | 72h matching window, manual match UI |
| ERP sync failure | GL entries missing | Retry queue, reconciliation reports |
| Image corruption | OCR fails | Quality check on upload, re-upload prompt |

### Multi-Tenancy Considerations
- Row-level security via tenant_id on all tables
- Separate S3 prefixes per tenant for receipts
- Policy rules scoped to tenant (no cross-tenant leakage)
- Rate limiting per tenant to prevent noisy-neighbor

### Compliance & Audit
- Immutable audit log for all state transitions
- Receipt retention: 7 years minimum (IRS requirements)
- GDPR: Employee data deletion with receipt anonymization
- SOX compliance: Segregation of duties in approval chains

### Security
- Receipt images encrypted at rest (AES-256)
- PII masking in logs (credit card numbers on receipts)
- Role-based access: employees see own, managers see team, finance sees all
- API authentication: OAuth2 + tenant-scoped JWT

## 11. Trade-offs & Alternatives

| Decision | Choice | Alternative | Reasoning |
|----------|--------|-------------|-----------|
| OCR Engine | AWS Textract | Self-hosted Tesseract | Accuracy > cost for financial docs |
| Policy storage | PostgreSQL JSONB | Custom DSL compiler | Flexibility for tenant-specific rules |
| Receipt storage | S3 + CDN | Database BLOB | Cost-effective at scale, direct URL access |
| Event bus | Kafka | RabbitMQ | Durability + replay for audit trails |
| Search | Elasticsearch | PostgreSQL FTS | Complex queries across expense fields |
| ML Categorization | Fine-tuned BERT | Rule-based | Handles merchant name variations better |

### Scaling Strategy
- **Phase 1** (< 100K expenses/mo): Single region, shared PostgreSQL
- **Phase 2** (< 1M expenses/mo): Read replicas, dedicated OCR cluster
- **Phase 3** (< 10M expenses/mo): Sharding by tenant_id, multi-region
- **Phase 4** (> 10M expenses/mo): Dedicated infrastructure per large tenant
