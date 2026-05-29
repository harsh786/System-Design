# Secrets Management Platform (like HashiCorp Vault)

## 1. Requirements

### Functional Requirements
- Secret storage: key-value secrets, dynamic secrets, PKI certificates
- Encryption as a service (transit engine): encrypt/decrypt without exposing keys
- Access policies: path-based ACL with fine-grained permissions
- Audit logging: every secret access logged with requestor identity
- Lease management: TTL-based secret expiry with renewal
- Secret rotation: automated rotation for databases, cloud credentials
- Seal/unseal mechanism: protect master encryption key
- Multi-cloud/multi-cluster secret distribution
- Disaster recovery and replication
- Namespaces for multi-tenancy
- Secret versioning with rollback capability
- Authentication backends (LDAP, OIDC, Kubernetes, AWS IAM, certificates)

### Non-Functional Requirements
- Secret retrieval latency < 10ms (p99)
- Zero plaintext secrets at rest (encrypted with master key)
- 99.999% availability for secret reads
- Audit log completeness: 100% of operations logged
- Support 1M+ secret reads/second across cluster
- Key rotation without downtime
- FIPS 140-2 Level 3 compliance for key storage

## 2. Core Entities

```
Secret: path, version, data (encrypted), metadata, created_at, destroyed (bool)
SecretEngine: path_prefix, type (kv/transit/pki/database/cloud), config
Lease: lease_id, path, ttl, renewable, issued_at, expires_at, revoked
Policy: name, rules[] (path pattern, capabilities[])
Token: token_id, accessor, policies[], ttl, renewable, metadata, parent_token
AuthMethod: path, type (userpass/ldap/oidc/k8s/aws/cert), config
AuditDevice: type (file/syslog/socket), config, format (json/jsonx)
SealConfig: type (shamir/awskms/gcpkms/transit), key_shares, key_threshold
EncryptionKey: name, version, type (aes256-gcm/chacha20/rsa), min_decryption_version
Namespace: path, parent, policies[], auth_methods[]
```

## 3. API Design

### Secret Read/Write (KV v2)
```
POST /v1/secret/data/production/database/postgres
X-Vault-Token: s.AbCdEf123456
Content-Type: application/json

Request:
{
  "options": { "cas": 3 },
  "data": {
    "username": "app_service",
    "password": "s3cur3P@ss!2024",
    "host": "postgres-primary.internal",
    "port": 5432,
    "connection_string": "postgresql://app_service:s3cur3P@ss!2024@postgres-primary.internal:5432/appdb"
  }
}

Response (200):
{
  "request_id": "req-abc123",
  "lease_id": "",
  "renewable": false,
  "data": {
    "created_time": "2024-01-15T10:00:00.000Z",
    "custom_metadata": null,
    "deletion_time": "",
    "destroyed": false,
    "version": 4
  }
}
```

```
GET /v1/secret/data/production/database/postgres?version=4
X-Vault-Token: s.AbCdEf123456

Response (200):
{
  "request_id": "req-def456",
  "lease_id": "",
  "renewable": false,
  "data": {
    "data": {
      "username": "app_service",
      "password": "s3cur3P@ss!2024",
      "host": "postgres-primary.internal",
      "port": 5432
    },
    "metadata": {
      "created_time": "2024-01-15T10:00:00.000Z",
      "version": 4,
      "destroyed": false
    }
  }
}
```

### Transit Engine (Encryption as a Service)
```
POST /v1/transit/encrypt/payment-data
X-Vault-Token: s.AbCdEf123456

Request:
{
  "plaintext": "cGF5bWVudF9jYXJkXzQyNDJfNDI0Ml80MjQyXzQyNDI=",
  "context": "cGF5bWVudC1zZXJ2aWNl",
  "key_version": 3
}

Response (200):
{
  "data": {
    "ciphertext": "vault:v3:HpZ3MmNOHEqL2bNiSm9O...",
    "key_version": 3
  }
}

POST /v1/transit/decrypt/payment-data
X-Vault-Token: s.AbCdEf123456

Request:
{
  "ciphertext": "vault:v3:HpZ3MmNOHEqL2bNiSm9O...",
  "context": "cGF5bWVudC1zZXJ2aWNl"
}

Response (200):
{
  "data": {
    "plaintext": "cGF5bWVudF9jYXJkXzQyNDJfNDI0Ml80MjQyXzQyNDI="
  }
}
```

### Dynamic Secrets (Database)
```
GET /v1/database/creds/readonly-role
X-Vault-Token: s.AbCdEf123456

Response (200):
{
  "request_id": "req-ghi789",
  "lease_id": "database/creds/readonly-role/abc123def456",
  "renewable": true,
  "lease_duration": 3600,
  "data": {
    "username": "v-token-readonly-role-abc123-1705312800",
    "password": "A1b2C3d4-E5f6G7h8-I9j0K1l2"
  }
}
```

### Lease Renewal
```
POST /v1/sys/leases/renew
X-Vault-Token: s.AbCdEf123456

Request:
{
  "lease_id": "database/creds/readonly-role/abc123def456",
  "increment": 3600
}

Response (200):
{
  "lease_id": "database/creds/readonly-role/abc123def456",
  "renewable": true,
  "lease_duration": 3600
}
```

### PKI - Issue Certificate
```
POST /v1/pki/issue/web-server
X-Vault-Token: s.AbCdEf123456

Request:
{
  "common_name": "api.example.com",
  "alt_names": "api-v2.example.com,api-internal.example.com",
  "ttl": "720h",
  "format": "pem"
}

Response (200):
{
  "data": {
    "certificate": "-----BEGIN CERTIFICATE-----\nMIIC...",
    "issuing_ca": "-----BEGIN CERTIFICATE-----\nMIIB...",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...",
    "serial_number": "3a:b2:c4:d5:e6:f7:08:19",
    "expiration": 1707904800
  },
  "lease_id": "pki/issue/web-server/xyz789",
  "lease_duration": 2592000,
  "renewable": false
}
```

### Seal/Unseal Operations
```
PUT /v1/sys/unseal
Request:
{
  "key": "base64-encoded-key-share-1"
}

Response (200):
{
  "type": "shamir",
  "initialized": true,
  "sealed": true,
  "t": 3,
  "n": 5,
  "progress": 1,
  "nonce": "abc123",
  "version": "1.15.0"
}

// After threshold (3) shares provided:
Response (200):
{
  "type": "shamir",
  "initialized": true,
  "sealed": false,
  "t": 3,
  "n": 5,
  "progress": 0,
  "version": "1.15.0",
  "cluster_name": "vault-prod-east"
}
```

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      SECRETS MANAGEMENT PLATFORM                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │ App (SDK)│  │ CI/CD    │  │ Kubernetes│  │  Admin   │                    │
│  │          │  │ Pipeline │  │  Sidecar  │  │  CLI     │                    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                    │
│       │              │              │              │                          │
│       └──────────────┴──────┬───────┴──────────────┘                         │
│                             │  (HTTPS / mTLS)                                │
│                             │                                                │
│                    ┌────────▼────────┐                                       │
│                    │  Load Balancer  │                                       │
│                    └────────┬────────┘                                       │
│                             │                                                │
│    ┌────────────────────────┼────────────────────────┐                       │
│    │                        │                        │                       │
│    ▼                        ▼                        ▼                       │
│ ┌──────────┐         ┌──────────┐         ┌──────────┐                      │
│ │  Vault   │         │  Vault   │         │  Vault   │                      │
│ │  Node 1  │◄───────►│  Node 2  │◄───────►│  Node 3  │                      │
│ │ (Active) │  Raft   │(Standby) │  Raft   │(Standby) │                      │
│ ├──────────┤         ├──────────┤         ├──────────┤                      │
│ │ Barrier  │         │ Barrier  │         │ Barrier  │                      │
│ │ (Encrypt)│         │ (Encrypt)│         │ (Encrypt)│                      │
│ ├──────────┤         ├──────────┤         ├──────────┤                      │
│ │ Storage  │         │ Storage  │         │ Storage  │                      │
│ │ Backend  │         │ Backend  │         │ Backend  │                      │
│ └────┬─────┘         └────┬─────┘         └────┬─────┘                      │
│      │                    │                    │                              │
│      └────────────────────┼────────────────────┘                             │
│                           │                                                  │
│                    ┌──────▼──────┐                                           │
│                    │  Integrated │                                           │
│                    │  Raft Storage│                                          │
│                    │  (Encrypted) │                                          │
│                    └─────────────┘                                           │
│                                                                              │
│  ┌─────────────────────────────────────────────┐                            │
│  │              Secret Engines                  │                            │
│  │  ┌─────┐ ┌───────┐ ┌─────┐ ┌────────┐     │                            │
│  │  │ KV  │ │Transit│ │ PKI │ │Database│     │                            │
│  │  │Store│ │Engine │ │ CA  │ │Dynamic │     │                            │
│  │  └─────┘ └───────┘ └─────┘ └────────┘     │                            │
│  └─────────────────────────────────────────────┘                            │
│                                                                              │
│  ┌─────────────────────────────────────────────┐                            │
│  │              Auth Methods                    │                            │
│  │  ┌──────┐ ┌────┐ ┌────┐ ┌───┐ ┌─────┐    │                            │
│  │  │Token │ │OIDC│ │K8s │ │AWS│ │Cert │    │                            │
│  │  └──────┘ └────┘ └────┘ └───┘ └─────┘    │                            │
│  └─────────────────────────────────────────────┘                            │
│                                                                              │
│  ┌──────────────┐                                                           │
│  │ Audit Devices│ ──→ Kafka (audit-log topic) ──→ SIEM                     │
│  └──────────────┘                                                           │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 5. Deep Dive: Seal/Unseal Architecture

```python
class SealManager:
    """
    Manages the seal/unseal lifecycle using Shamir's Secret Sharing.
    The master key encrypts the encryption key which encrypts all data.
    
    Key hierarchy:
    Shamir Shares → Master Key → Encryption Key → Data
    """
    
    def __init__(self, config):
        self.config = config
        self.sealed = True
        self.master_key = None
        self.encryption_key = None
        self.unseal_progress = []
    
    def initialize(self, key_shares=5, key_threshold=3):
        """
        Initialize vault: generate master key, split with Shamir's.
        This is done ONCE during initial setup (ceremony).
        """
        # Generate master key (256-bit)
        master_key = os.urandom(32)
        
        # Generate encryption key
        encryption_key = os.urandom(32)
        
        # Encrypt the encryption key with master key
        encrypted_enc_key = self._encrypt_aes_gcm(master_key, encryption_key)
        
        # Split master key using Shamir's Secret Sharing
        shares = self._shamir_split(master_key, key_shares, key_threshold)
        
        # Store encrypted encryption key (this is persisted)
        self._store_keyring(encrypted_enc_key)
        
        # Return shares to operators (NEVER stored by vault)
        return InitResult(
            shares=[base64.b64encode(s).decode() for s in shares],
            shares_count=key_shares,
            threshold=key_threshold,
            root_token=self._generate_root_token()
        )
    
    def unseal(self, key_share):
        """
        Submit a key share toward unsealing.
        Once threshold shares collected, vault unseals.
        """
        if not self.sealed:
            return UnsealResult(sealed=False)
        
        share = base64.b64decode(key_share)
        self.unseal_progress.append(share)
        
        if len(self.unseal_progress) >= self.config.key_threshold:
            # Reconstruct master key
            master_key = self._shamir_combine(
                self.unseal_progress[:self.config.key_threshold]
            )
            
            # Decrypt the encryption key
            encrypted_enc_key = self._load_keyring()
            try:
                self.encryption_key = self._decrypt_aes_gcm(master_key, encrypted_enc_key)
                self.master_key = master_key
                self.sealed = False
                self.unseal_progress = []
                return UnsealResult(sealed=False, progress=0)
            except DecryptionError:
                self.unseal_progress = []
                raise InvalidKeyShareError("Reconstructed key is invalid")
        
        return UnsealResult(
            sealed=True,
            progress=len(self.unseal_progress),
            threshold=self.config.key_threshold
        )
    
    def _shamir_split(self, secret, n, k):
        """
        Shamir's Secret Sharing: split secret into n shares,
        any k shares can reconstruct the secret.
        Uses polynomial interpolation over GF(2^8).
        """
        # Generate random polynomial of degree k-1
        # where constant term = secret byte
        shares = [bytearray(len(secret)) for _ in range(n)]
        
        for byte_idx in range(len(secret)):
            # Random coefficients for polynomial
            coefficients = [secret[byte_idx]] + [
                random.randint(0, 255) for _ in range(k - 1)
            ]
            
            # Evaluate polynomial at points 1, 2, ..., n
            for share_idx in range(n):
                x = share_idx + 1
                y = self._evaluate_polynomial_gf256(coefficients, x)
                shares[share_idx][byte_idx] = y
        
        return [bytes(s) for s in shares]
    
    def _shamir_combine(self, shares):
        """Reconstruct secret from k shares using Lagrange interpolation."""
        secret_length = len(shares[0])
        secret = bytearray(secret_length)
        
        # Points are 1-indexed (1, 2, 3, ...)
        points = list(range(1, len(shares) + 1))
        
        for byte_idx in range(secret_length):
            y_values = [shares[i][byte_idx] for i in range(len(shares))]
            # Lagrange interpolation at x=0 to recover constant term
            secret[byte_idx] = self._lagrange_interpolate_gf256(points, y_values, 0)
        
        return bytes(secret)


class AutoUnseal:
    """
    Auto-unseal using cloud KMS (AWS KMS, GCP KMS, Azure Key Vault).
    Eliminates manual key share management.
    """
    
    def __init__(self, kms_config):
        self.kms_client = self._create_kms_client(kms_config)
        self.kms_key_id = kms_config.key_id
    
    async def unseal(self):
        """
        Auto-unseal: master key encrypted by cloud KMS.
        Vault calls KMS to decrypt master key on startup.
        """
        # Load KMS-encrypted master key from storage
        encrypted_master = self._load_encrypted_master_key()
        
        # Call cloud KMS to decrypt
        master_key = await self.kms_client.decrypt(
            key_id=self.kms_key_id,
            ciphertext=encrypted_master,
            context={'vault_cluster': self.cluster_name}
        )
        
        return master_key
    
    async def seal_wrap(self, plaintext, context):
        """
        Seal-wrap: individually encrypt high-security items with KMS.
        Used for root tokens, master key material.
        """
        return await self.kms_client.encrypt(
            key_id=self.kms_key_id,
            plaintext=plaintext,
            context=context
        )


class RekeyOperation:
    """
    Rekey: generate new master key and re-split with new shares.
    Used when key holders change or threshold needs updating.
    """
    
    async def start_rekey(self, new_shares, new_threshold):
        """Initiate rekey operation (requires existing threshold to authorize)."""
        self.rekey_config = RekeyConfig(
            new_shares=new_shares,
            new_threshold=new_threshold,
            nonce=generate_nonce(),
            progress=[]
        )
        return RekeyInitResult(
            nonce=self.rekey_config.nonce,
            required_shares=self.current_threshold
        )
    
    async def submit_rekey_share(self, share, nonce):
        """Submit share toward rekey authorization."""
        if nonce != self.rekey_config.nonce:
            raise InvalidNonceError()
        
        self.rekey_config.progress.append(share)
        
        if len(self.rekey_config.progress) >= self.current_threshold:
            # Verify existing shares reconstruct current master key
            reconstructed = shamir_combine(self.rekey_config.progress)
            if reconstructed != self.master_key:
                raise InvalidSharesError()
            
            # Generate new master key
            new_master = os.urandom(32)
            
            # Re-encrypt the encryption key with new master
            new_encrypted_enc_key = encrypt_aes_gcm(new_master, self.encryption_key)
            
            # Split new master key
            new_shares = shamir_split(
                new_master,
                self.rekey_config.new_shares,
                self.rekey_config.new_threshold
            )
            
            # Persist new keyring
            self._store_keyring(new_encrypted_enc_key)
            self.master_key = new_master
            
            return RekeyResult(
                shares=new_shares,
                shares_count=self.rekey_config.new_shares,
                threshold=self.rekey_config.new_threshold
            )
```

## 6. Deep Dive: Dynamic Secrets

```python
class DynamicSecretEngine:
    """
    Generate on-demand, short-lived credentials.
    Each credential has a lease and is automatically revoked on expiry.
    """
    
    def __init__(self, lease_manager):
        self.lease_manager = lease_manager
        self.backends = {}
    
    async def generate_credentials(self, role, request_info):
        """Generate dynamic credentials for a role."""
        backend = self.backends[role.backend_type]
        
        # Generate unique credentials
        creds = await backend.create_credentials(role)
        
        # Create lease for automatic revocation
        lease = await self.lease_manager.create_lease(
            path=f"{role.backend_type}/creds/{role.name}",
            ttl=role.default_ttl,
            max_ttl=role.max_ttl,
            renewable=True,
            revoke_func=lambda: backend.revoke_credentials(creds),
            data={'username': creds.username, 'role': role.name}
        )
        
        return DynamicCredentialResult(
            username=creds.username,
            password=creds.password,
            lease_id=lease.id,
            lease_duration=role.default_ttl,
            renewable=True
        )


class PostgresBackend:
    """Dynamic credential backend for PostgreSQL."""
    
    async def create_credentials(self, role):
        """Create a temporary database user with role's permissions."""
        username = f"v-{role.token_display}-{role.name}-{self._random_suffix()}"
        password = self._generate_password(32)
        
        # Execute creation SQL (templated from role config)
        creation_sql = role.creation_statements.format(
            name=username,
            password=password,
            expiration=self._calculate_expiry(role.default_ttl)
        )
        
        async with self.pool.acquire() as conn:
            await conn.execute(creation_sql)
        
        return Credentials(username=username, password=password)
    
    async def revoke_credentials(self, creds):
        """Revoke credentials by dropping the database user."""
        async with self.pool.acquire() as conn:
            # Terminate active connections
            await conn.execute(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE usename = '{creds.username}'
            """)
            # Revoke and drop
            await conn.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {creds.username}")
            await conn.execute(f"DROP ROLE IF EXISTS {creds.username}")
    
    async def rotate_root(self, config):
        """Rotate the root credentials used by Vault to manage users."""
        new_password = self._generate_password(32)
        
        async with self.pool.acquire() as conn:
            await conn.execute(f"ALTER ROLE {config.username} PASSWORD '{new_password}'")
        
        # Update stored config (Vault stores the new root password)
        config.password = new_password
        return config


class LeaseManager:
    """
    Track and manage all active leases.
    Handles renewal, revocation, and expiry.
    """
    
    def __init__(self, storage, clock):
        self.storage = storage
        self.clock = clock
        self.expiry_queue = PriorityQueue()  # Min-heap by expiry time
    
    async def create_lease(self, path, ttl, max_ttl, renewable, revoke_func, data):
        """Create a new lease."""
        lease_id = self._generate_lease_id(path)
        now = self.clock.now()
        
        lease = Lease(
            id=lease_id,
            path=path,
            issued_at=now,
            expires_at=now + ttl,
            max_expires_at=now + max_ttl,
            ttl=ttl,
            renewable=renewable,
            revoke_func=revoke_func
        )
        
        await self.storage.store_lease(lease)
        self.expiry_queue.push(lease.expires_at, lease_id)
        
        return lease
    
    async def renew_lease(self, lease_id, increment):
        """Renew a lease (extend its TTL)."""
        lease = await self.storage.get_lease(lease_id)
        
        if not lease:
            raise LeaseNotFoundError(lease_id)
        if not lease.renewable:
            raise LeaseNotRenewableError(lease_id)
        
        now = self.clock.now()
        if now >= lease.expires_at:
            raise LeaseExpiredError(lease_id)
        
        # Cannot exceed max TTL
        new_expiry = min(now + increment, lease.max_expires_at)
        lease.expires_at = new_expiry
        
        await self.storage.update_lease(lease)
        return lease
    
    async def revoke_lease(self, lease_id):
        """Immediately revoke a lease and clean up credentials."""
        lease = await self.storage.get_lease(lease_id)
        if not lease:
            return
        
        # Call the revocation function (e.g., drop database user)
        try:
            await lease.revoke_func()
        except Exception as e:
            # Log but don't fail - mark for retry
            await self._mark_revocation_failed(lease_id, e)
            return
        
        await self.storage.delete_lease(lease_id)
    
    async def expire_leases(self):
        """Background job: revoke expired leases."""
        now = self.clock.now()
        
        while not self.expiry_queue.empty():
            expiry_time, lease_id = self.expiry_queue.peek()
            if expiry_time > now:
                break
            
            self.expiry_queue.pop()
            await self.revoke_lease(lease_id)


class CredentialRotation:
    """Automated secret rotation without downtime."""
    
    async def rotate_secret(self, path, rotation_config):
        """
        Rotate a secret using double-write pattern:
        1. Generate new credential
        2. Write as new version
        3. Verify new credential works
        4. Allow grace period for old credential
        5. Revoke old credential
        """
        # Generate new credentials
        new_creds = await self._generate_new_credentials(rotation_config)
        
        # Write as new version (old version still valid)
        await self.kv_store.write(path, new_creds, cas=True)
        
        # Verify new credentials work
        verified = await self._verify_credentials(new_creds, rotation_config)
        if not verified:
            # Rollback: destroy new version
            await self.kv_store.destroy_version(path, version='latest')
            raise RotationVerificationError(path)
        
        # Schedule old credential revocation after grace period
        await self.scheduler.schedule(
            delay=rotation_config.grace_period,
            action=self._revoke_old_credentials,
            args=(rotation_config, path)
        )
```

## 7. Deep Dive: Transit Engine

```python
class TransitEngine:
    """
    Encryption as a Service: applications encrypt/decrypt data
    without ever seeing the encryption keys.
    
    Supports: AES256-GCM, ChaCha20-Poly1305, RSA-OAEP, ED25519
    """
    
    def __init__(self, key_storage):
        self.key_storage = key_storage
    
    async def encrypt(self, key_name, plaintext, context=None, key_version=None):
        """
        Encrypt data using named key.
        Context enables key derivation for multi-tenant isolation.
        """
        key = await self.key_storage.get_key(key_name)
        
        if key_version:
            key_material = key.get_version(key_version)
        else:
            key_material = key.get_latest()
        
        # Derive key if context provided (key derivation)
        if context:
            derived_key = self._derive_key(key_material, context)
        else:
            derived_key = key_material.key_bytes
        
        # Encrypt with AES-256-GCM
        nonce = os.urandom(12)
        cipher = AES_GCM(derived_key, nonce)
        ciphertext = cipher.encrypt(base64.b64decode(plaintext))
        
        # Format: vault:v{version}:{base64(nonce + ciphertext + tag)}
        blob = nonce + ciphertext
        formatted = f"vault:v{key_material.version}:{base64.b64encode(blob).decode()}"
        
        return EncryptResult(ciphertext=formatted, key_version=key_material.version)
    
    async def decrypt(self, key_name, ciphertext, context=None):
        """Decrypt vault-encrypted ciphertext."""
        # Parse version from ciphertext
        parts = ciphertext.split(':')
        version = int(parts[1][1:])  # "v3" → 3
        blob = base64.b64decode(parts[2])
        
        key = await self.key_storage.get_key(key_name)
        key_material = key.get_version(version)
        
        # Check min decryption version
        if version < key.min_decryption_version:
            raise KeyVersionTooOldError(
                f"Key version {version} below minimum {key.min_decryption_version}"
            )
        
        # Derive key if context provided
        if context:
            derived_key = self._derive_key(key_material, context)
        else:
            derived_key = key_material.key_bytes
        
        # Decrypt
        nonce = blob[:12]
        ciphertext_bytes = blob[12:]
        cipher = AES_GCM(derived_key, nonce)
        plaintext = cipher.decrypt(ciphertext_bytes)
        
        return DecryptResult(plaintext=base64.b64encode(plaintext).decode())
    
    async def rotate_key(self, key_name):
        """
        Rotate encryption key: new version for encryption,
        old versions still available for decryption.
        """
        key = await self.key_storage.get_key(key_name)
        new_version = key.latest_version + 1
        new_key_bytes = os.urandom(32)
        
        key.add_version(KeyVersion(
            version=new_version,
            key_bytes=new_key_bytes,
            created_at=time.time()
        ))
        
        await self.key_storage.save_key(key)
        return KeyRotationResult(key_name=key_name, new_version=new_version)
    
    def _derive_key(self, key_material, context):
        """
        HKDF-based key derivation for context-specific encryption.
        Enables multi-tenant isolation with single master key.
        """
        return hkdf_sha256(
            ikm=key_material.key_bytes,
            salt=None,
            info=base64.b64decode(context),
            length=32
        )
    
    async def rewrap(self, key_name, ciphertext, new_version=None):
        """
        Re-encrypt data with latest key version without exposing plaintext.
        Used during key rotation to upgrade old ciphertexts.
        """
        # Decrypt with old key version
        plaintext = await self.decrypt(key_name, ciphertext)
        
        # Re-encrypt with new/latest version
        return await self.encrypt(key_name, plaintext.plaintext, key_version=new_version)


class ConvergentEncryption:
    """
    Convergent encryption: same plaintext + context always produces
    same ciphertext. Enables tokenization and searching on encrypted data.
    """
    
    async def encrypt_convergent(self, key_name, plaintext, context):
        """
        Deterministic encryption using derived nonce.
        WARNING: Leaks equality (same input = same output).
        """
        key = await self.key_storage.get_key(key_name)
        key_material = key.get_latest()
        
        # Derive key from context
        derived_key = self._derive_key(key_material, context)
        
        # Derive nonce deterministically from plaintext + key
        nonce = hmac_sha256(derived_key, base64.b64decode(plaintext))[:12]
        
        # Encrypt (deterministic because nonce is derived)
        cipher = AES_GCM(derived_key, nonce)
        ciphertext = cipher.encrypt(base64.b64decode(plaintext))
        
        blob = nonce + ciphertext
        return f"vault:v{key_material.version}:{base64.b64encode(blob).decode()}"
```

## 8. Database Schema

### Storage Backend (Encrypted at rest)

```sql
-- All values encrypted with the encryption key before storage
-- Vault uses a generic KV store interface

-- Logical entries (stored encrypted)
CREATE TABLE vault_entries (
    path            VARCHAR(2048) PRIMARY KEY,
    value           BYTEA NOT NULL,  -- AES-256-GCM encrypted
    version         BIGINT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Secret versions (KV v2)
CREATE TABLE secret_versions (
    path            VARCHAR(2048) NOT NULL,
    version         INT NOT NULL,
    data_encrypted  BYTEA NOT NULL,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL,
    deletion_time   TIMESTAMPTZ,
    destroyed       BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (path, version),
    INDEX idx_path (path)
);

-- Leases
CREATE TABLE leases (
    lease_id        VARCHAR(512) PRIMARY KEY,
    path            VARCHAR(2048) NOT NULL,
    token_id        VARCHAR(128) NOT NULL,
    issued_at       TIMESTAMPTZ NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    max_expires_at  TIMESTAMPTZ NOT NULL,
    renewable       BOOLEAN DEFAULT TRUE,
    revoke_data     BYTEA,  -- Encrypted revocation info
    INDEX idx_expiry (expires_at),
    INDEX idx_token (token_id),
    INDEX idx_path (path)
);

-- Tokens
CREATE TABLE tokens (
    id              VARCHAR(128) PRIMARY KEY,
    accessor        VARCHAR(128) UNIQUE NOT NULL,
    parent_id       VARCHAR(128),
    policies        TEXT[] NOT NULL,
    path            VARCHAR(2048),
    metadata        JSONB,
    ttl             INT,  -- seconds
    max_ttl         INT,
    created_at      TIMESTAMPTZ NOT NULL,
    expires_at      TIMESTAMPTZ,
    num_uses        INT DEFAULT 0,
    max_uses        INT,
    INDEX idx_accessor (accessor),
    INDEX idx_parent (parent_id),
    INDEX idx_expiry (expires_at)
);

-- Policies
CREATE TABLE policies (
    name            VARCHAR(256) PRIMARY KEY,
    rules           TEXT NOT NULL,  -- HCL or JSON policy document
    version         INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    type            VARCHAR(32) NOT NULL,  -- request, response
    auth_type       VARCHAR(64),
    auth_accessor   VARCHAR(128),
    auth_policies   TEXT[],
    path            VARCHAR(2048),
    operation       VARCHAR(32),
    remote_address  INET,
    request_data    JSONB,  -- Sensitive fields HMAC'd, not stored raw
    response_data   JSONB,
    error           TEXT,
    INDEX idx_timestamp (timestamp DESC),
    INDEX idx_path (path, timestamp DESC),
    INDEX idx_accessor (auth_accessor, timestamp DESC)
) PARTITION BY RANGE (timestamp);

-- Encryption keys (transit engine)
CREATE TABLE transit_keys (
    name            VARCHAR(256) PRIMARY KEY,
    type            VARCHAR(32) NOT NULL,  -- aes256-gcm96, chacha20, rsa-2048
    latest_version  INT NOT NULL DEFAULT 1,
    min_decryption_version INT DEFAULT 1,
    min_encryption_version INT DEFAULT 0,
    deletion_allowed BOOLEAN DEFAULT FALSE,
    exportable      BOOLEAN DEFAULT FALSE,
    allow_plaintext_backup BOOLEAN DEFAULT FALSE,
    convergent      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE transit_key_versions (
    key_name        VARCHAR(256) NOT NULL REFERENCES transit_keys(name),
    version         INT NOT NULL,
    key_material    BYTEA NOT NULL,  -- Double encrypted (master key → encryption key → material)
    created_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (key_name, version)
);
```

## 9. Kafka & Redis Configuration

### Kafka Configuration

```yaml
# Kafka - Audit log streaming and event distribution
topics:
  vault-audit-log:
    partitions: 16
    replication_factor: 3
    retention_ms: 7776000000  # 90 days
    cleanup_policy: delete
    compression_type: zstd
    min_insync_replicas: 2  # Audit completeness guarantee
    # Audit must not lose events
    
  vault-events:
    partitions: 8
    replication_factor: 3
    retention_ms: 604800000  # 7 days
    cleanup_policy: delete
    
  lease-revocations:
    partitions: 16
    replication_factor: 3
    retention_ms: 86400000  # 24 hours
    cleanup_policy: delete

  secret-rotation-commands:
    partitions: 8
    replication_factor: 3
    retention_ms: 86400000

producer:
  acks: all  # Audit must not be lost
  retries: 2147483647  # Infinite retries for audit
  enable_idempotence: true
  max_in_flight_requests: 1
  compression_type: zstd

consumer:
  group_id: vault-audit-processor
  auto_offset_reset: earliest
  enable_auto_commit: false
  max_poll_records: 500
```

### Redis Configuration

```yaml
redis:
  cluster:
    nodes: 6
    node_memory: 8GB
    maxmemory_policy: noeviction
    # TLS required for all connections
    tls_enabled: true
    tls_cert_file: /etc/vault/tls/redis-client.crt
    tls_key_file: /etc/vault/tls/redis-client.key
  
  key_patterns:
    # Token lookup cache (encrypted in Redis too)
    token_cache: "vault:token:{accessor}"  # TTL: min(token_ttl, 300s)
    
    # Lease expiry tracking (sorted set)
    lease_expiry: "vault:leases:expiry"  # ZSET: score=expiry_unix, value=lease_id
    
    # Rate limiting per client
    rate_limit: "vault:rate:{client_ip}"  # Sliding window
    
    # Response cache for hot paths (encrypted)
    response_cache: "vault:cache:{path_hash}"  # TTL: 30s
    
    # Active request dedup (prevent replay)
    request_nonce: "vault:nonce:{nonce}"  # TTL: 60s

  scripts:
    # Atomic lease expiry check
    pop_expired_leases: |
      local now = tonumber(ARGV[1])
      local batch_size = tonumber(ARGV[2])
      local expired = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', now, 'LIMIT', 0, batch_size)
      if #expired > 0 then
        redis.call('ZREM', KEYS[1], unpack(expired))
      end
      return expired
```

## 10. Scalability & Performance

### Read Performance
- **Performance standbys**: Non-active nodes serve read requests directly
- **Response caching**: Hot secret paths cached in Redis (encrypted)
- **Connection pooling**: Persistent connections for database backends
- **Batch API**: Read multiple secrets in single request

### Write Performance
- **Single active node**: All writes through Raft leader (consistency)
- **Write-ahead log**: Raft log batching (group commit)
- **Async audit**: Audit log written to Kafka asynchronously (blocking configurable)

### Dynamic Secret Scaling
- **Connection pooling**: Vault maintains pool to backend databases
- **Credential pre-generation**: Pre-create credentials during low load
- **Lease coalescing**: Group lease expirations to reduce revocation storms

### Capacity Planning
```
1M secret reads/second:
- Active node: 100K reads/sec (limited by crypto operations)
- Performance standbys: 10 nodes × 100K = 1M reads/sec
- Transit engine: 50K encrypt/decrypt ops/sec per node (AES-NI)
- Dynamic secrets: 1K credential generations/sec (database limited)
- Storage: 10M secrets × 1KB avg = 10GB encrypted storage
```

## 11. Failure Handling & Reliability

### Active Node Failure
- Raft election selects new active (< 5 seconds)
- In-flight requests fail, clients retry to new active
- Performance standbys continue serving cached reads during election

### Auto-Unseal KMS Failure
- Vault remains operational while unsealed (keys in memory)
- If vault restarts during KMS outage → remains sealed until KMS recovers
- Multi-KMS: configure secondary KMS for failover

### Lease Revocation Failure
- Retry queue for failed revocations (exponential backoff)
- Dead letter after N failures → manual intervention required
- Force revocation: drop credentials even if backend unreachable

### Storage Backend Failure
- Raft integrated storage: replicated across 3+ nodes
- Snapshot every 10K transactions for fast recovery
- Cross-region replication for DR (async, < 1s lag)

### Security Incident Response
- Emergency seal: immediately seal vault (clears master key from memory)
- Token revocation tree: revoking parent revokes all children
- Audit log tamper detection: HMAC chain verification
- Lease revocation prefix: revoke all credentials for a path

### Disaster Recovery
- DR replication: async streaming of encrypted storage to remote cluster
- Promotion: DR secondary promoted to primary in < 60 seconds
- RPO: < 1 second (bounded by replication lag)
- RTO: < 60 seconds (promotion + unseal)
- Backup: periodic snapshots to encrypted object storage
