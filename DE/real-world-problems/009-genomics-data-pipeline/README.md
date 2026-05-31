# Problem 9: Genomics Data Pipeline

### Problem 9: Genomics Data Pipeline
```
SCALE: 1 TB per genome, 1000 genomes/day
ARCH: Raw FASTQ → BWA alignment (HPC) → Variant calling → Delta Lake
WHY SPARK: Embarrassingly parallel (each chromosome independent)
STORAGE: S3 + Hail (genomics-specific format)
```
