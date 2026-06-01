# Healthcare EHR Data Interoperability Pipeline at Epic/Cerner Scale

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. The Problem: 500 Hospitals × 100M Patients → Unified Clinical Data Lake

### Business Context

A large integrated delivery network (IDN) formed through decades of acquisitions
now operates 500 hospitals and 2,000+ clinics. Each facility brought its own EHR
system. Clinical data is siloed — a patient seen at three facilities has three
separate records with no unified longitudinal view.

**Goal**: Build a single, HIPAA-compliant clinical data lake using OMOP Common
Data Model to enable population health analytics, clinical trial matching,
quality reporting, and outcomes research across the entire health system.

### Scale Parameters

```
┌─────────────────────────────────┬──────────────────────────────────────────┐
│ Parameter                       │ Value                                    │
├─────────────────────────────────┼──────────────────────────────────────────┤
│ Hospitals                       │ 500                                      │
│ Clinics / Ambulatory Sites      │ 2,000+                                   │
│ Total Patients                  │ 100M unique individuals                  │
│ Clinical Events per Day         │ 10 billion (labs, vitals, Rx, notes)     │
│ Source EHR Systems              │ Epic, Cerner, Athena, AllScripts, custom │
│ Data Formats                    │ 200+ (HL7v2, FHIR R4, CDA, X12, DICOM)  │
│ Target Model                    │ OMOP CDM v5.4                            │
│ Terminology Systems             │ SNOMED-CT, ICD-10-CM, LOINC, RxNorm, CPT│
│ Retention Requirement           │ 10 years minimum (legal hold: forever)   │
│ PHI Fields per Record           │ 18 Safe Harbor identifiers               │
│ Compliance Frameworks           │ HIPAA, HITECH, 21st Century Cures, ONC   │
│ Latency Requirement             │ < 4 hours for clinical decision support  │
│ Availability                    │ 99.95% (clinical safety dependency)      │
└─────────────────────────────────┴──────────────────────────────────────────┘
```

### Why This Matters

- **Population Health**: Identify at-risk cohorts across 100M patients
- **Clinical Trials**: Match patients to trials based on unified conditions/medications
- **Quality Reporting**: CMS Star Ratings, HEDIS measures require complete data
- **Outcomes Research**: Compare treatment efficacy across diverse populations
- **Care Coordination**: Prevent duplicate tests, dangerous drug interactions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 2. Why Traditional Approaches Fail

### Point-to-Point Integration (N² Problem)

```
500 systems × 499 targets = 249,500 interfaces
Each interface needs: mapping, testing, monitoring, versioning
Maintenance cost: $50K/interface/year = $12.5B annually (impossible)
```

### Single-Format Mandate

- Epic won't expose native data in Cerner format
- Vendors lock in proprietary extensions to FHIR
- Migration timelines: 3-7 years per hospital
- Patient care cannot wait for format unification

### Manual ETL Scripts

- 200+ formats × annual version changes = unmaintainable
- HL7v2 alone has 50+ message types, each with optional segments
- One developer can maintain ~5 complex format parsers
- Staff turnover destroys institutional knowledge

### Cloud Data Warehouse Only

- HIPAA BAA complexity with PHI in transit
- Cannot handle semi-structured HL7v2/CDA natively
- Row-level consent enforcement is a bolted-on afterthought
- Real-time HL7 feeds don't fit batch DW patterns

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    HEALTHCARE EHR INTEROPERABILITY PIPELINE                       │
└──────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────── SOURCE SYSTEMS ───────────────────────┐
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │   Epic   │  │  Cerner  │  │  Athena  │  │AllScripts│    │
│  │ (200 hosp)│  │(150 hosp)│  │(100 hosp)│  │ (50 hosp)│    │
│  │ FHIR R4  │  │  HL7v2   │  │ CDA XML  │  │  HL7v2   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │          │
│  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐    │
│  │Lab Systems│  │ Pharmacy │  │ Imaging  │  │  Claims  │    │
│  │(HL7 ORM/ │  │ (NCPDP)  │  │ (DICOM)  │  │(X12 837) │    │
│  │   ORU)   │  │          │  │          │  │          │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │          │
└───────┼──────────────┼──────────────┼──────────────┼──────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER                                │
│                                                                    │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ AWS MSK     │  │ API Gateway  │  │ AWS Transfer Family   │    │
│  │ (HL7 feeds) │  │ (FHIR REST)  │  │ (SFTP batch files)    │    │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬───────────┘    │
│         │                 │                      │                 │
│         └─────────────────┼──────────────────────┘                │
│                           ▼                                        │
│              ┌────────────────────────┐                           │
│              │   S3 Raw Landing Zone  │                           │
│              │  (KMS-CMK encrypted)   │                           │
│              │  s3://ehr-raw-phi/     │                           │
│              └───────────┬────────────┘                           │
└──────────────────────────┼────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         AWS GLUE PIPELINE (5 JOBS)                            │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │ JOB 1: Multi-Format Ingestion & Classification                        │   │
│  │                                                                        │   │
│  │  Custom Classifiers:                                                   │   │
│  │  • HL7v2 Classifier (pipe-delimited, MSH segment detection)           │   │
│  │  • FHIR JSON Classifier (resourceType + Bundle detection)             │   │
│  │  • CDA XML Classifier (ClinicalDocument root element)                 │   │
│  │  • X12 EDI Classifier (ISA/GS/ST envelope detection)                  │   │
│  │  • DICOM Classifier (metadata JSON extraction)                        │   │
│  │                                                                        │   │
│  │  Output: Classified, validated raw records → S3 staged/                │   │
│  └───────────────────────────────┬───────────────────────────────────────┘   │
│                                  │                                            │
│                                  ▼                                            │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │ JOB 2: FHIR R4 Normalization                                          │   │
│  │                                                                        │   │
│  │  • HL7v2 → FHIR R4 (segment-by-segment mapping)                      │   │
│  │  • CDA → FHIR R4 (section/entry → resource mapping)                  │   │
│  │  • X12 → FHIR R4 (claim → ExplanationOfBenefit)                      │   │
│  │  • Vendor extensions → FHIR extensions (Epic MyChart, Cerner PowerChart)│  │
│  │                                                                        │   │
│  │  Output: Canonical FHIR R4 Bundles (Parquet) → S3 normalized/         │   │
│  └───────────────────────────────┬───────────────────────────────────────┘   │
│                                  │                                            │
│                                  ▼                                            │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │ JOB 3: Patient Matching & Deduplication (MPI)                         │   │
│  │                                                                        │   │
│  │  • Blocking: Last name + DOB + Gender → candidate pairs               │   │
│  │  • Scoring: Fellegi-Sunter probabilistic (name, SSN, address, phone)  │   │
│  │  • Thresholds: >0.95 = auto-link, 0.80-0.95 = manual review          │   │
│  │  • Enterprise MPI: Golden record creation                             │   │
│  │                                                                        │   │
│  │  Output: Linked patient graph → S3 mpi/                               │   │
│  └───────────────────────────────┬───────────────────────────────────────┘   │
│                                  │                                            │
│                                  ▼                                            │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │ JOB 4: Terminology Standardization                                     │   │
│  │                                                                        │   │
│  │  Crosswalk Tables:                                                     │   │
│  │  • Local codes → SNOMED-CT (diagnoses, findings)                      │   │
│  │  • ICD-9 → ICD-10-CM (legacy migration)                              │   │
│  │  • Local lab codes → LOINC (observations)                             │   │
│  │  • NDC → RxNorm (medications)                                         │   │
│  │  • Local procedures → CPT/HCPCS                                       │   │
│  │                                                                        │   │
│  │  Output: Standardized coded records → S3 standardized/                │   │
│  └───────────────────────────────┬───────────────────────────────────────┘   │
│                                  │                                            │
│                                  ▼                                            │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │ JOB 5: OMOP CDM Transformation                                        │   │
│  │                                                                        │   │
│  │  Target Tables:                                                        │   │
│  │  • person (demographics)                                               │   │
│  │  • condition_occurrence (diagnoses)                                    │   │
│  │  • drug_exposure (medications)                                         │   │
│  │  • measurement (labs, vitals)                                          │   │
│  │  • procedure_occurrence (surgeries, imaging)                           │   │
│  │  • observation (social history, assessments)                           │   │
│  │  • visit_occurrence (encounters)                                       │   │
│  │  • note_nlp (extracted clinical concepts)                             │   │
│  │                                                                        │   │
│  │  Output: OMOP CDM Iceberg tables → S3 omop-cdm/                      │   │
│  └───────────────────────────────┬───────────────────────────────────────┘   │
│                                  │                                            │
└──────────────────────────────────┼────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CONSUMERS                                            │
│                                                                                │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  ┌────────────┐  │
│  │Clinical Research│  │Population Health│  │Quality Report │  │Trial Match │  │
│  │ Athena/Trino   │  │   Redshift     │  │  CMS/HEDIS   │  │  ML/SageMkr│  │
│  │ (ad-hoc SQL)   │  │ (dashboards)   │  │ (automated)  │  │ (matching) │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  └────────────┘  │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4. Glue Concepts Used

### Custom Classifiers for Healthcare Formats

```
┌─────────────────────────────────────────────────────────────────┐
│ Classifier          │ Detection Logic                           │
├─────────────────────┼───────────────────────────────────────────┤
│ HL7v2               │ Starts with "MSH|^~\\&|", pipe-delimited │
│ FHIR JSON           │ Contains "resourceType", valid Bundle     │
│ CDA XML             │ Root element: <ClinicalDocument>          │
│ X12 EDI             │ Starts with ISA segment, fixed-width      │
│ DICOM Metadata      │ JSON with StudyInstanceUID field          │
└─────────────────────┴───────────────────────────────────────────┘
```

### DynamicFrame for Nested FHIR Resources

FHIR resources are deeply nested — a Patient resource contains arrays of
identifiers, addresses, telecom contacts, and extensions. A Bundle can contain
hundreds of resources with cross-references. DynamicFrame handles this without
requiring a pre-defined schema:

- Self-describing schema discovery for FHIR Bundles
- Relationalize() to flatten nested arrays (Patient.name[], Observation.component[])
- ResolveChoice for polymorphic FHIR value[x] fields (valueQuantity, valueString, etc.)

### Glue Connections

- **FHIR REST API**: Epic FHIR R4 endpoints (OAuth2 SMART on FHIR)
- **HL7 MLLP**: TCP connections to Cerner integration engines (via MSK)
- **SFTP**: Batch file drops from legacy systems (AWS Transfer Family)
- **JDBC**: AllScripts database extracts (read replicas)

### Security Configuration

```
┌──────────────────────────────────────────────────────────────┐
│ Layer              │ Control                                  │
├────────────────────┼──────────────────────────────────────────┤
│ Encryption at Rest │ KMS CMK (aws/glue alias forbidden)      │
│ Encryption Transit │ TLS 1.2+ enforced on all connections    │
│ Network            │ VPC endpoints (S3, Glue, KMS, STS)      │
│ Access             │ IAM roles per job, no long-term creds   │
│ Audit              │ CloudTrail + Glue job audit logs → SIEM │
│ Data Masking       │ Lake Formation column-level on PHI      │
│ Consent            │ Row-level filtering per patient consent │
└────────────────────┴──────────────────────────────────────────┘
```

### Lake Formation: PHI Access Control

- **Column-level masking**: SSN, MRN, address masked for research users
- **Row-level filtering**: Only show patients who consented to research
- **Tag-based access**: Resources tagged `phi=true` require elevated role
- **Cross-account**: Research partners get de-identified views only

### Glue Data Quality Rules

```python
ruleset = """
    Rules = [
        ColumnExists "person_id",
        IsComplete "birth_datetime",
        ColumnValues "gender_concept_id" in [8507, 8532, 8551],
        ColumnValues "condition_source_value" matches "^[A-Z][0-9]{2}\.?[0-9]*$",
        ColumnValues "measurement_date" between "1900-01-01" and "2025-12-31",
        CustomSql "SELECT COUNT(*) FROM primary WHERE person_id NOT IN 
                   (SELECT person_id FROM reference.person)" = 0
    ]
"""
```

### Schema Registry

- FHIR R4 resource profiles registered as Avro schemas
- US Core Implementation Guide profiles enforced
- Version evolution tracked (STU3 → R4 migration)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5. Implementation Code

### Job 1: HL7v2 Message Parsing

```python
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql import functions as F
from pyspark.sql.types import *

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'source_path', 'output_path'])
glueContext = GlueContext(SparkContext.getOrCreate())
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HL7v2 Message Parser - Handles ADT, ORM, ORU, MDM messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def parse_hl7v2_message(raw_message):
    """Parse HL7v2 pipe-delimited message into structured segments."""
    segments = {}
    lines = raw_message.strip().split('\r')
    
    for line in lines:
        fields = line.split('|')
        segment_id = fields[0]
        
        if segment_id == 'MSH':
            segments['msh'] = {
                'sending_application': fields[2] if len(fields) > 2 else None,
                'sending_facility': fields[3] if len(fields) > 3 else None,
                'receiving_application': fields[4] if len(fields) > 4 else None,
                'message_datetime': fields[6] if len(fields) > 6 else None,
                'message_type': fields[8] if len(fields) > 8 else None,
                'message_control_id': fields[9] if len(fields) > 9 else None,
                'version_id': fields[11] if len(fields) > 11 else None
            }
        elif segment_id == 'PID':
            segments['pid'] = {
                'patient_id': fields[3] if len(fields) > 3 else None,
                'patient_name': parse_hl7_name(fields[5]) if len(fields) > 5 else None,
                'date_of_birth': fields[7] if len(fields) > 7 else None,
                'gender': fields[8] if len(fields) > 8 else None,
                'race': fields[10] if len(fields) > 10 else None,
                'address': parse_hl7_address(fields[11]) if len(fields) > 11 else None,
                'phone_home': fields[13] if len(fields) > 13 else None,
                'ssn': fields[19] if len(fields) > 19 else None,
                'drivers_license': fields[20] if len(fields) > 20 else None
            }
        elif segment_id == 'OBX':
            if 'obx' not in segments:
                segments['obx'] = []
            segments['obx'].append({
                'set_id': fields[1] if len(fields) > 1 else None,
                'value_type': fields[2] if len(fields) > 2 else None,
                'observation_id': fields[3] if len(fields) > 3 else None,
                'observation_value': fields[5] if len(fields) > 5 else None,
                'units': fields[6] if len(fields) > 6 else None,
                'reference_range': fields[7] if len(fields) > 7 else None,
                'abnormal_flags': fields[8] if len(fields) > 8 else None,
                'observation_datetime': fields[14] if len(fields) > 14 else None
            })
        elif segment_id == 'DG1':
            if 'dg1' not in segments:
                segments['dg1'] = []
            segments['dg1'].append({
                'diagnosis_code': fields[3] if len(fields) > 3 else None,
                'diagnosis_description': fields[4] if len(fields) > 4 else None,
                'diagnosis_datetime': fields[5] if len(fields) > 5 else None,
                'diagnosis_type': fields[6] if len(fields) > 6 else None
            })
    
    return segments

def parse_hl7_name(name_field):
    """Parse HL7 XPN name format: Last^First^Middle^Suffix^Prefix."""
    parts = name_field.split('^')
    return {
        'family': parts[0] if len(parts) > 0 else None,
        'given': parts[1] if len(parts) > 1 else None,
        'middle': parts[2] if len(parts) > 2 else None,
        'suffix': parts[3] if len(parts) > 3 else None,
        'prefix': parts[4] if len(parts) > 4 else None
    }

def parse_hl7_address(addr_field):
    """Parse HL7 XAD address format."""
    parts = addr_field.split('^')
    return {
        'street': parts[0] if len(parts) > 0 else None,
        'city': parts[2] if len(parts) > 2 else None,
        'state': parts[3] if len(parts) > 3 else None,
        'zip': parts[4] if len(parts) > 4 else None,
        'country': parts[5] if len(parts) > 5 else None
    }

# Register UDF for distributed parsing
parse_hl7_udf = F.udf(parse_hl7v2_message, MapType(StringType(), StringType()))

# Read raw HL7v2 messages from S3
raw_hl7 = spark.read.text(f"{args['source_path']}/hl7v2/")

# Parse messages
parsed = raw_hl7.withColumn("segments", parse_hl7_udf(F.col("value")))

# Write to staging
parsed.write.mode("append").parquet(f"{args['output_path']}/staged/hl7v2/")
```

### Job 2: FHIR Bundle Flattening

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FHIR R4 Bundle Flattening - Handles deeply nested resources
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Read FHIR Bundles (JSON)
fhir_dyf = glueContext.create_dynamic_frame.from_options(
    connection_type="s3",
    connection_options={
        "paths": [f"{args['source_path']}/fhir/"],
        "recurse": True
    },
    format="json",
    format_options={"jsonPath": "$.entry[*].resource"}
)

# Resolve polymorphic value[x] fields in Observations
# FHIR uses value[x] where x can be Quantity, String, CodeableConcept, etc.
resolved = ResolveChoice.apply(
    frame=fhir_dyf,
    choice="match_catalog",
    transformation_ctx="resolve_fhir_polymorphic"
)

# Relationalize deeply nested structures
# Patient.name[] → patient_name table with FK
# Observation.component[] → observation_component table
relationalized = resolved.relationalize(
    root_table_name="fhir_resources",
    staging_path=f"{args['output_path']}/temp/relationalize/"
)

# Extract specific resource types
for resource_type in ['Patient', 'Condition', 'Observation', 'MedicationRequest',
                      'Procedure', 'Encounter', 'DiagnosticReport']:
    resource_df = relationalized.select(f"fhir_resources") \
        .toDF() \
        .filter(F.col("resourceType") == resource_type)
    
    resource_df.write \
        .mode("append") \
        .partitionBy("meta.lastUpdated_date") \
        .parquet(f"{args['output_path']}/normalized/{resource_type}/")

# Convert HL7v2 to FHIR R4
def hl7v2_to_fhir_patient(pid_segment):
    """Map HL7v2 PID segment to FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "identifier": [{
            "system": f"urn:oid:{pid_segment.get('sending_facility', '')}",
            "value": pid_segment.get('patient_id', '')
        }],
        "name": [{
            "family": pid_segment.get('patient_name', {}).get('family'),
            "given": [pid_segment.get('patient_name', {}).get('given')]
        }],
        "gender": map_hl7_gender(pid_segment.get('gender', '')),
        "birthDate": format_hl7_date(pid_segment.get('date_of_birth', '')),
        "address": [{
            "line": [pid_segment.get('address', {}).get('street')],
            "city": pid_segment.get('address', {}).get('city'),
            "state": pid_segment.get('address', {}).get('state'),
            "postalCode": pid_segment.get('address', {}).get('zip')
        }]
    }

def map_hl7_gender(hl7_gender):
    """Map HL7v2 gender codes to FHIR."""
    mapping = {'M': 'male', 'F': 'female', 'U': 'unknown', 'O': 'other'}
    return mapping.get(hl7_gender, 'unknown')
```

### Job 3: Patient Matching (Fellegi-Sunter)

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Probabilistic Patient Matching - Enterprise MPI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from pyspark.sql import Window
import math

# Fellegi-Sunter weights (derived from training data)
FIELD_WEIGHTS = {
    'ssn':        {'m': 9.5,  'u': -4.0},   # SSN match/non-match log-likelihood
    'dob':        {'m': 7.2,  'u': -3.5},
    'last_name':  {'m': 5.8,  'u': -2.1},
    'first_name': {'m': 4.5,  'u': -1.8},
    'gender':     {'m': 1.2,  'u': -0.5},
    'zip_code':   {'m': 3.1,  'u': -1.2},
    'phone':      {'m': 6.5,  'u': -3.0},
    'address':    {'m': 4.8,  'u': -2.0}
}

AUTO_LINK_THRESHOLD = 15.0    # Above = automatic link
MANUAL_REVIEW_THRESHOLD = 8.0 # Between = manual review queue
AUTO_NON_LINK = 8.0           # Below = definitely different

def compute_match_score(record_a, record_b):
    """Compute Fellegi-Sunter probabilistic match score."""
    score = 0.0
    
    for field, weights in FIELD_WEIGHTS.items():
        val_a = record_a.get(field)
        val_b = record_b.get(field)
        
        if val_a is None or val_b is None:
            continue  # Missing data: no contribution
        
        if field in ['last_name', 'first_name']:
            # Jaro-Winkler similarity for names
            similarity = jaro_winkler(val_a, val_b)
            if similarity > 0.92:
                score += weights['m']
            elif similarity < 0.70:
                score += weights['u']
            else:
                # Partial credit
                score += weights['m'] * (similarity - 0.70) / 0.22
        elif field == 'ssn':
            if val_a == val_b:
                score += weights['m']
            else:
                score += weights['u']
        elif field == 'dob':
            if val_a == val_b:
                score += weights['m']
            elif val_a[:4] == val_b[:4]:  # Same year
                score += weights['m'] * 0.3
            else:
                score += weights['u']
        else:
            if val_a == val_b:
                score += weights['m']
            else:
                score += weights['u']
    
    return score

# Step 1: Blocking (reduce comparison space)
# Block on: first 3 chars of last name + year of birth + gender
patients_df = spark.read.parquet(f"{args['source_path']}/normalized/Patient/")

patients_blocked = patients_df.withColumn(
    "blocking_key",
    F.concat(
        F.substring(F.upper(F.col("name_family")), 1, 3),
        F.substring(F.col("birth_date"), 1, 4),
        F.col("gender")
    )
)

# Step 2: Generate candidate pairs within blocks
candidate_pairs = patients_blocked.alias("a").join(
    patients_blocked.alias("b"),
    (F.col("a.blocking_key") == F.col("b.blocking_key")) &
    (F.col("a.source_id") < F.col("b.source_id")),  # Avoid duplicates
    "inner"
)

# Step 3: Score pairs
match_score_udf = F.udf(compute_match_score, FloatType())

scored_pairs = candidate_pairs.withColumn(
    "match_score",
    match_score_udf(
        F.struct([F.col(f"a.{c}") for c in FIELD_WEIGHTS.keys()]),
        F.struct([F.col(f"b.{c}") for c in FIELD_WEIGHTS.keys()])
    )
)

# Step 4: Classify matches
auto_links = scored_pairs.filter(F.col("match_score") >= AUTO_LINK_THRESHOLD)
manual_review = scored_pairs.filter(
    (F.col("match_score") >= MANUAL_REVIEW_THRESHOLD) &
    (F.col("match_score") < AUTO_LINK_THRESHOLD)
)

# Step 5: Write results
auto_links.write.mode("append").parquet(f"{args['output_path']}/mpi/auto_linked/")
manual_review.write.mode("append").parquet(f"{args['output_path']}/mpi/manual_review/")
```

### Job 4: Terminology Standardization

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Terminology Mapping - SNOMED, ICD-10, LOINC, RxNorm, CPT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Load crosswalk tables (maintained by terminology team)
snomed_icd10_xwalk = spark.read.parquet("s3://ehr-terminology/crosswalks/snomed_to_icd10/")
local_to_loinc = spark.read.parquet("s3://ehr-terminology/crosswalks/local_lab_to_loinc/")
ndc_to_rxnorm = spark.read.parquet("s3://ehr-terminology/crosswalks/ndc_to_rxnorm/")
local_to_snomed = spark.read.parquet("s3://ehr-terminology/crosswalks/local_to_snomed/")

# Broadcast small crosswalks for efficient joins
snomed_icd10_bc = F.broadcast(snomed_icd10_xwalk)
local_loinc_bc = F.broadcast(local_to_loinc)

# Map conditions: local codes → SNOMED-CT → ICD-10-CM
conditions = spark.read.parquet(f"{args['source_path']}/normalized/Condition/")

standardized_conditions = conditions \
    .join(
        local_to_snomed,
        (conditions.source_code == local_to_snomed.local_code) &
        (conditions.source_system == local_to_snomed.source_system),
        "left"
    ) \
    .join(
        snomed_icd10_bc,
        F.coalesce(F.col("snomed_code"), F.col("source_code")) == snomed_icd10_bc.snomed_concept_id,
        "left"
    ) \
    .select(
        conditions["*"],
        F.coalesce(F.col("snomed_code"), F.col("source_code")).alias("standard_concept_code"),
        F.lit("SNOMED-CT").alias("standard_vocabulary"),
        F.col("icd10_code").alias("mapped_icd10"),
        F.col("mapping_confidence")
    )

# Map lab results: local codes → LOINC
observations = spark.read.parquet(f"{args['source_path']}/normalized/Observation/")

standardized_labs = observations \
    .join(
        local_loinc_bc,
        (observations.observation_code == local_loinc_bc.local_lab_code) &
        (observations.source_facility == local_loinc_bc.facility_id),
        "left"
    ) \
    .withColumn(
        "standard_loinc",
        F.coalesce(F.col("loinc_code"), F.col("observation_code"))
    )

# Map medications: NDC → RxNorm
medications = spark.read.parquet(f"{args['source_path']}/normalized/MedicationRequest/")

standardized_meds = medications \
    .join(ndc_to_rxnorm, medications.medication_code == ndc_to_rxnorm.ndc_code, "left") \
    .withColumn(
        "standard_rxnorm",
        F.coalesce(F.col("rxnorm_cui"), F.col("medication_code"))
    )

# Track unmapped codes for terminology team review
unmapped_conditions = standardized_conditions.filter(F.col("standard_concept_code").isNull())
unmapped_conditions.write.mode("append").parquet(f"{args['output_path']}/unmapped/conditions/")
```

### Job 5: OMOP CDM Transformation

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OMOP Common Data Model v5.4 Transformation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from pyspark.sql.functions import monotonically_increasing_id

# Load MPI (golden records from Job 3)
mpi = spark.read.parquet(f"{args['source_path']}/mpi/golden_records/")

# ── PERSON table ──
person_df = mpi.select(
    F.col("enterprise_person_id").alias("person_id"),
    F.when(F.col("gender") == "male", 8507)
     .when(F.col("gender") == "female", 8532)
     .otherwise(8551).alias("gender_concept_id"),
    F.year(F.col("birth_date")).alias("year_of_birth"),
    F.month(F.col("birth_date")).alias("month_of_birth"),
    F.dayofmonth(F.col("birth_date")).alias("day_of_birth"),
    F.col("birth_date").cast("timestamp").alias("birth_datetime"),
    F.col("race_concept_id"),
    F.col("ethnicity_concept_id"),
    F.col("location_id"),
    F.col("primary_source_system").alias("person_source_value")
)

# ── CONDITION_OCCURRENCE table ──
condition_occurrence = standardized_conditions \
    .join(mpi, "source_patient_id") \
    .select(
        monotonically_increasing_id().alias("condition_occurrence_id"),
        F.col("enterprise_person_id").alias("person_id"),
        F.col("snomed_concept_id").alias("condition_concept_id"),
        F.col("onset_date").alias("condition_start_date"),
        F.col("onset_datetime").alias("condition_start_datetime"),
        F.col("abatement_date").alias("condition_end_date"),
        F.lit(32817).alias("condition_type_concept_id"),  # EHR
        F.col("source_code").alias("condition_source_value"),
        F.col("source_concept_id").alias("condition_source_concept_id"),
        F.col("encounter_id").alias("visit_occurrence_id")
    )

# ── DRUG_EXPOSURE table ──
drug_exposure = standardized_meds \
    .join(mpi, "source_patient_id") \
    .select(
        monotonically_increasing_id().alias("drug_exposure_id"),
        F.col("enterprise_person_id").alias("person_id"),
        F.col("rxnorm_concept_id").alias("drug_concept_id"),
        F.col("authored_on").alias("drug_exposure_start_date"),
        F.col("dispense_end_date").alias("drug_exposure_end_date"),
        F.lit(32838).alias("drug_type_concept_id"),  # EHR prescription
        F.col("dosage_text").alias("sig"),
        F.col("quantity"),
        F.col("days_supply"),
        F.col("ndc_code").alias("drug_source_value"),
        F.col("encounter_id").alias("visit_occurrence_id")
    )

# ── MEASUREMENT table ──
measurement = standardized_labs \
    .join(mpi, "source_patient_id") \
    .select(
        monotonically_increasing_id().alias("measurement_id"),
        F.col("enterprise_person_id").alias("person_id"),
        F.col("loinc_concept_id").alias("measurement_concept_id"),
        F.col("effective_date").alias("measurement_date"),
        F.col("effective_datetime").alias("measurement_datetime"),
        F.lit(32856).alias("measurement_type_concept_id"),  # Lab
        F.col("value_quantity").alias("value_as_number"),
        F.col("value_codeable_concept_id").alias("value_as_concept_id"),
        F.col("unit_concept_id"),
        F.col("reference_range_low").alias("range_low"),
        F.col("reference_range_high").alias("range_high"),
        F.col("local_lab_code").alias("measurement_source_value"),
        F.col("encounter_id").alias("visit_occurrence_id")
    )

# Write OMOP tables as Iceberg
for table_name, df in [("person", person_df),
                        ("condition_occurrence", condition_occurrence),
                        ("drug_exposure", drug_exposure),
                        ("measurement", measurement)]:
    df.writeTo(f"glue_catalog.omop_cdm.{table_name}") \
      .tableProperty("format-version", "2") \
      .partitionedBy("year_of_birth" if table_name == "person" else "measurement_date") \
      .createOrReplace()
```

### PHI De-identification (Safe Harbor Method)

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Safe Harbor De-identification - 18 HIPAA Identifiers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import hashlib
from datetime import timedelta
import random

# Per-patient date shift (consistent within patient, random across patients)
# Shift range: -365 to +365 days
def get_date_shift(person_id, salt):
    """Deterministic but unpredictable date shift per patient."""
    hash_input = f"{person_id}:{salt}".encode()
    hash_val = int(hashlib.sha256(hash_input).hexdigest()[:8], 16)
    return (hash_val % 731) - 365  # -365 to +365

def deidentify_safe_harbor(df, person_id_col, date_shift_salt):
    """Apply Safe Harbor de-identification to a DataFrame."""
    
    deidentified = df \
        .drop("patient_name", "ssn", "mrn", "phone", "fax",
              "email", "ip_address", "device_serial", "url",
              "drivers_license", "account_number", "certificate_number",
              "vehicle_id", "biometric_id", "photo") \
        .withColumn(
            "zip_code",
            F.when(F.col("zip_code").isNotNull(),
                   F.substring(F.col("zip_code"), 1, 3) + "00")
             .otherwise(None)
        ) \
        .withColumn(
            "birth_date_shifted",
            F.expr(f"date_add(birth_date, get_date_shift({person_id_col}, '{date_shift_salt}'))")
        ) \
        .withColumn(
            "age_over_89",
            F.when(F.col("age") > 89, F.lit(True)).otherwise(F.lit(False))
        ) \
        .withColumn(
            "age_safe",
            F.when(F.col("age") > 89, F.lit(90)).otherwise(F.col("age"))
        ) \
        .drop("birth_date", "age")
    
    return deidentified
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. Production Handling

### Schema Variations Between EHR Vendors

```
┌────────────────────────────────────────────────────────────────────────┐
│ Field              │ Epic                │ Cerner              │ Athena │
├────────────────────┼─────────────────────┼─────────────────────┼────────┤
│ Patient ID         │ FHIR Patient.id     │ PID-3 (CX format)  │ CDA id │
│ Encounter Type     │ class (code system) │ PV1-2 (I/O/E)      │ code   │
│ Diagnosis          │ Condition resource  │ DG1 segment         │ entry  │
│ Medication         │ MedicationRequest   │ RXE segment         │ entry  │
│ Lab Result         │ Observation         │ OBX segment         │ entry  │
│ Timestamps         │ ISO 8601            │ HL7 DTM (YYYYMMDD) │ HL7 TS │
│ Coded Values       │ FHIR CodeableConcept│ CE (code^desc^sys) │ CD     │
└────────────────────┴─────────────────────┴─────────────────────┴────────┘
```

**Strategy**: Abstract vendor differences in Job 2 (normalization). Each vendor
gets a dedicated mapper class. New vendors add a new mapper without changing
downstream logic.

### Corrections & Amendments

Clinical records are never deleted — they are amended. FHIR `_history` provides
version tracking. The pipeline handles:

- **Corrections**: Overwrite the record with `status: entered-in-error` on the original
- **Amendments**: New version with `meta.versionId` incremented
- **Late-arriving data**: Merge into existing encounter using temporal ordering
- **Iceberg time-travel**: Previous versions accessible via snapshot history

### Patient Merge/Unmerge Events

```python
# Handle ADT^A40 (merge) and ADT^A41 (unmerge) events
def handle_patient_merge(merge_event):
    surviving_id = merge_event['surviving_patient_id']
    merged_id = merge_event['merged_patient_id']
    
    # Update MPI: point merged_id → surviving_id
    # Rewrite OMOP person_id references in all clinical tables
    # Maintain merge history for audit trail
    # Propagate to downstream consumers via CDC
```

### Terminology Version Updates

- ICD-10-CM updates annually (October 1)
- SNOMED-CT releases biannually
- Pipeline runs dual-version lookups during transition periods
- Historical data retains original codes; `_mapped_version` column tracks crosswalk version

### HIPAA Audit Logging

```python
# Every PHI access logged to immutable audit trail
audit_record = {
    "timestamp": "2024-03-15T14:30:22Z",
    "user_arn": "arn:aws:iam::123456789:role/clinical-researcher",
    "action": "READ",
    "resource": "omop_cdm.condition_occurrence",
    "patient_ids_accessed": ["P-12345", "P-67890"],
    "columns_accessed": ["condition_source_value", "person_id"],
    "phi_columns_accessed": [],
    "justification": "IRB-2024-0042",
    "query_hash": "sha256:abc123..."
}
```

### Data Quality Quarantine

Records failing validation are quarantined, not dropped:

- Invalid ICD-10 codes → quarantine + alert terminology team
- Future dates → quarantine + alert source system admin
- Missing required fields → quarantine + request re-send (HL7 NACK)
- Duplicate messages → deduplicate using MSH-10 control ID

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7. Compliance

### HIPAA Security Rule

```
┌──────────────────────────────────────────────────────────────────┐
│ Safeguard          │ Implementation                              │
├────────────────────┼─────────────────────────────────────────────┤
│ Access Control     │ IAM roles, Lake Formation, MFA required     │
│ Audit Controls     │ CloudTrail, Glue job logs, S3 access logs   │
│ Integrity          │ S3 Object Lock (WORM), Iceberg snapshots    │
│ Transmission       │ TLS 1.2+, VPC endpoints, no public egress  │
│ Encryption         │ KMS CMK (AES-256), key rotation annual      │
│ Risk Assessment    │ Quarterly review of Glue job permissions    │
└────────────────────┴─────────────────────────────────────────────┘
```

### HIPAA Privacy Rule

- **Minimum Necessary**: Lake Formation grants only columns needed per role
- **Patient Consent**: Row-level filtering respects opt-out flags
- **Accounting of Disclosures**: Every query against PHI logged
- **Business Associate Agreements**: AWS BAA covers Glue, S3, KMS

### HITECH Act

- **Breach Notification**: Automated detection of unauthorized access patterns
- **Meaningful Use**: Pipeline enables quality measure calculation (eCQMs)
- **Health Information Exchange**: Supports TEFCA framework queries

### 21st Century Cures Act

- **Information Blocking**: Pipeline ensures data flows to authorized consumers
- **Patient Access**: FHIR R4 layer supports patient-facing apps
- **Standardized APIs**: US Core IG compliance in normalization layer

### ONC Interoperability Requirements

- USCDI v3 data elements fully mapped
- Bulk FHIR ($export) compatible output
- Provenance tracking on all transformations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8. Scaling to 10B Clinical Events/Day

### Partition Strategy

```
s3://ehr-omop-cdm/
  └── condition_occurrence/
      └── institution_id=HOSP001/
          └── condition_start_date=2024-03-15/
              └── part-00001.parquet

Partition keys:
  - institution_id (500 values) → enables per-hospital processing
  - event_date (daily) → enables time-range pruning
  - Iceberg hidden partitioning: month(condition_start_date)
```

### Parallel Execution

```
┌────────────────────────────────────────────────────────────────┐
│ Strategy                    │ Implementation                    │
├─────────────────────────────┼───────────────────────────────────┤
│ Per-hospital parallelism    │ Glue Workflow triggers 500 jobs   │
│ Auto-scaling DPUs           │ G.2X workers, 2-100 per job       │
│ Patient matching batching   │ 1M patients per batch, 100 batches│
│ Terminology lookups         │ Broadcast join (crosswalks < 1GB) │
│ Iceberg compaction          │ Nightly async compaction job      │
│ Backfill isolation          │ Separate job queue, lower priority│
└─────────────────────────────┴───────────────────────────────────┘
```

### Patient Matching at Scale

- **Blocking reduces comparisons**: 100M patients → ~500M candidate pairs (vs 5×10¹⁵ brute force)
- **Batch processing**: Divide into cohorts by blocking key prefix
- **Incremental matching**: New patients only compared to existing golden records
- **Graph-based transitivity**: If A=B and B=C, then A=C (union-find)

### Throughput Numbers

```
10B events/day ÷ 24 hours = 416M events/hour
Peak: 2x average = 833M events/hour (morning lab results)
At 50 G.2X DPUs per job × 5 jobs = 250 DPUs sustained
Burst capacity: 1000 DPUs across all concurrent jobs
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9. Cost Analysis

### Monthly Breakdown

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Component                          │ Units              │ Monthly Cost     │
├────────────────────────────────────┼────────────────────┼──────────────────┤
│ Glue DPUs (G.2X)                   │ 250 avg × 730 hrs │ $80,300          │
│ Glue DPUs (burst)                  │ 500 peak × 200 hrs│ $44,000          │
│ Glue Crawlers                      │ 500 sources × daily│ $2,200          │
│ Glue Data Quality                  │ 10B evaluations    │ $10,000          │
│ S3 Storage (raw + processed)       │ 800 TB             │ $18,400          │
│ S3 Requests (GET/PUT)              │ 50B requests       │ $25,000          │
│ KMS (CMK operations)               │ 100B encrypt/decrypt│ $3,000          │
│ Lake Formation                     │ Included with Glue │ $0               │
│ MSK (HL7 streaming)                │ 6 brokers          │ $7,200           │
│ CloudWatch (logging/metrics)       │ 5 TB logs          │ $2,500           │
│ Data transfer (VPC endpoints)      │ 100 TB internal    │ $1,000           │
├────────────────────────────────────┼────────────────────┼──────────────────┤
│ TOTAL                              │                    │ ~$193,600/month  │
│ Per patient per month              │ 100M patients      │ $0.0019          │
│ Annual                             │                    │ ~$2.3M           │
└────────────────────────────────────┴────────────────────┴──────────────────┘
```

### Comparison with Alternatives

```
┌────────────────────────────────────────────────────────────────────────┐
│ Solution                   │ Annual Cost  │ Notes                      │
├────────────────────────────┼──────────────┼────────────────────────────┤
│ AWS Glue (this pipeline)   │ $2.3M        │ Fully managed, auto-scale  │
│ Informatica CDGC           │ $8-12M       │ License + infrastructure   │
│ MuleSoft Healthcare Hub    │ $5-8M        │ Per-connection pricing     │
│ Custom Spark on EMR        │ $3.5M        │ More ops overhead          │
│ InterSystems HealthShare   │ $6-10M       │ Per-hospital licensing     │
│ Rhapsody Integration Engine│ $4-7M        │ Per-interface pricing      │
└────────────────────────────┴──────────────┴────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 10. Companies Running Similar Pipelines

| Company | Scale | Stack | Use Case |
|---------|-------|-------|----------|
| **Epic Systems** | 250M+ patients (MyChart) | Internal + Azure | Cosmos DB integration, Care Everywhere network |
| **Oracle Health (Cerner)** | 200M+ patients | Oracle Cloud + custom | Millennium data migration to cloud-native |
| **Intermountain Healthcare** | 2.5M patients, 24 hospitals | AWS (Glue + Redshift) | Population health, genomics integration |
| **Kaiser Permanente** | 12.5M members | Hybrid (on-prem + cloud) | HealthConnect analytics, clinical trials |
| **NHS Digital** | 65M patients (entire UK) | AWS + Azure hybrid | National Data Platform, COVID dashboards |
| **Mayo Clinic** | 1.3M patients/year | AWS + GCP | Clinical Data Warehouse, research platform |
| **Humana** | 17M members | AWS (Glue + SageMaker) | Claims + clinical for Star Ratings |
| **Flatiron Health** | 3M+ cancer patients | AWS | Oncology research, real-world evidence |
| **Tempus** | 7M+ clinical records | GCP + custom | Genomics + EHR for precision medicine |
| **Health Catalyst** | 100+ health systems | AWS | DOS platform, OMOP-based analytics |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Key Takeaways

1. **Healthcare interoperability is a data engineering problem** — not just a standards problem. FHIR alone doesn't solve the 200+ format reality.

2. **Patient matching is the hardest sub-problem** — probabilistic linking at 100M scale requires careful blocking, scoring, and manual review workflows.

3. **OMOP CDM as the target model** enables network studies across institutions using standardized analytics tools (ATLAS, ACHILLES).

4. **Compliance is not a feature — it's the architecture** — encryption, access control, audit logging, and consent enforcement must be baked into every layer.

5. **Glue's value proposition**: managed infrastructure that handles the heterogeneous format problem (custom classifiers, DynamicFrame for nested data) while providing enterprise security (KMS, Lake Formation, VPC) required for PHI.
