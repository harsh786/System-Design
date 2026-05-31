# Problem 75: Cost-Effective Historical Data Archival

### Problem 75: Cost-Effective Historical Data Archival
```
TIERING:
  Hot (0-7 days): SSD storage, instant queries ($0.10/GB)
  Warm (7-90 days): HDD/S3 Standard, seconds to query ($0.023/GB)
  Cold (90d-1yr): S3 IA, minutes to access ($0.0125/GB)
  Archive (1yr+): Glacier Deep Archive, hours to restore ($0.00099/GB)

AUTOMATION:
  • S3 Lifecycle policies move data automatically
  • Delta Lake OPTIMIZE compacts before archival
  • Metadata stays in catalog (queryable even if archived)
  • Restore-on-demand for investigations
```
