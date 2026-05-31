# Storage And File Systems

Back to [HLD Problem Bank](../README.md).

Object storage, distributed file systems, backup, metadata, sync, deduplication, replication, and durability tradeoffs.

## Problems

- [051. Object storage like S3](051-object-storage-like-s3.md) - buckets, object metadata, durability, erasure coding, multipart upload
- [052. Dropbox](052-dropbox.md) - block sync, dedupe, conflict resolution, offline clients
- [053. Google Drive](053-google-drive.md) - permissions, sharing, versioning, sync, search
- [054. A distributed file system like GFS/HDFS](054-distributed-file-system-like-gfs-hdfs.md) - master metadata, chunk servers, replication, consistency
- [055. Backup and restore platform](055-backup-and-restore-platform.md) - snapshots, retention, restore tests, encryption, ransomware recovery
- [056. A photo/file metadata service](056-photo-file-metadata-service.md) - metadata indexing, ACLs, search, versioning
- [057. A file upload service for large files](057-file-upload-service-for-large-files.md) - multipart upload, resumability, checksums, malware scanning
- [058. A document versioning system](058-document-versioning-system.md) - immutable versions, diffs, conflict resolution, retention
- [059. A distributed key-value store](059-distributed-key-value-store.md) - consistent hashing, replication, quorum, vector clocks
- [060. A blob storage lifecycle manager](060-blob-storage-lifecycle-manager.md) - tiering, TTL, archival, deletion, compliance holds
