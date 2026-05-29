import java.util.*;
import java.io.*;
import java.nio.file.*;

/**
 * Problem 63: Write-Ahead Log (WAL) with Recovery
 * 
 * PRODUCTION MAPPING: PostgreSQL WAL, MySQL redo log, SQLite journal,
 *                     etcd, ZooKeeper transaction log, Kafka commit log
 * 
 * Core Principle: Write changes to a durable log BEFORE applying to state.
 * On crash, replay the log to recover consistent state.
 * 
 * Design Decisions:
 * - Sequential writes only (fast on disk, even HDD)
 * - Log structured: LSN (Log Sequence Number) for ordering
 * - Checkpointing: truncate log after state is durably persisted
 * - fsync on commit for durability guarantee
 * 
 * Trade-offs:
 * - fsync every write: durable but slow (~100-200 writes/sec on HDD)
 * - Group commit: batch fsyncs for throughput (PostgreSQL does this)
 * - Checkpoint frequency: more often = faster recovery, less log space
 * 
 * Recovery modes:
 * - Redo-only: replay all committed ops since last checkpoint
 * - Undo-redo: can also rollback uncommitted transactions
 */
public class Problem63_WriteAheadLog {

    enum LogRecordType { BEGIN, WRITE, COMMIT, ABORT, CHECKPOINT }

    static class LogRecord implements Serializable {
        final long lsn;           // Log Sequence Number
        final LogRecordType type;
        final String txnId;
        final String key;
        final String oldValue;    // for undo
        final String newValue;    // for redo
        final long timestamp;

        LogRecord(long lsn, LogRecordType type, String txnId, String key, 
                  String oldValue, String newValue) {
            this.lsn = lsn;
            this.type = type;
            this.txnId = txnId;
            this.key = key;
            this.oldValue = oldValue;
            this.newValue = newValue;
            this.timestamp = System.currentTimeMillis();
        }

        @Override
        public String toString() {
            return String.format("LSN=%d [%s] txn=%s key=%s %s->%s", 
                lsn, type, txnId, key, oldValue, newValue);
        }
    }

    static class WriteAheadLog {
        private final List<LogRecord> log = new ArrayList<>(); // simulates file
        private long nextLSN = 1;
        private long checkpointLSN = 0;
        private final Map<String, String> state; // the actual database state
        private final Map<String, Map<String, String>> activeTxns = new HashMap<>(); // txnId -> writes

        public WriteAheadLog() {
            this.state = new HashMap<>();
        }

        // ---- Transaction API ----
        public String beginTransaction() {
            String txnId = "txn-" + UUID.randomUUID().toString().substring(0, 8);
            appendLog(LogRecordType.BEGIN, txnId, null, null, null);
            activeTxns.put(txnId, new LinkedHashMap<>());
            return txnId;
        }

        public void write(String txnId, String key, String value) {
            if (!activeTxns.containsKey(txnId)) throw new IllegalStateException("No active txn: " + txnId);
            String oldValue = state.get(key);
            appendLog(LogRecordType.WRITE, txnId, key, oldValue, value);
            // Apply to state immediately (write-ahead, state updated)
            state.put(key, value);
            activeTxns.get(txnId).put(key, oldValue); // remember old value for undo
        }

        public void commit(String txnId) {
            if (!activeTxns.containsKey(txnId)) throw new IllegalStateException("No active txn");
            appendLog(LogRecordType.COMMIT, txnId, null, null, null);
            activeTxns.remove(txnId);
            // In real system: fsync here guarantees durability
        }

        public void abort(String txnId) {
            Map<String, String> writes = activeTxns.remove(txnId);
            if (writes == null) return;
            // Undo all writes in reverse
            List<String> keys = new ArrayList<>(writes.keySet());
            Collections.reverse(keys);
            for (String key : keys) {
                String oldValue = writes.get(key);
                if (oldValue == null) state.remove(key);
                else state.put(key, oldValue);
            }
            appendLog(LogRecordType.ABORT, txnId, null, null, null);
        }

        // ---- Checkpoint ----
        public void checkpoint() {
            appendLog(LogRecordType.CHECKPOINT, null, null, null, null);
            checkpointLSN = nextLSN - 1;
        }

        // ---- Recovery (ARIES-simplified) ----
        /**
         * Recover state from log after a "crash".
         * 1. Redo all committed transactions since checkpoint
         * 2. Undo all uncommitted transactions
         */
        public static WriteAheadLog recover(List<LogRecord> savedLog) {
            WriteAheadLog wal = new WriteAheadLog();
            wal.log.addAll(savedLog);
            wal.nextLSN = savedLog.isEmpty() ? 1 : savedLog.get(savedLog.size() - 1).lsn + 1;

            // Find last checkpoint
            long lastCheckpointLSN = 0;
            for (LogRecord r : savedLog) {
                if (r.type == LogRecordType.CHECKPOINT) lastCheckpointLSN = r.lsn;
            }

            // Determine committed and uncommitted txns
            Set<String> committed = new HashSet<>();
            Set<String> started = new HashSet<>();
            for (LogRecord r : savedLog) {
                if (r.lsn < lastCheckpointLSN) continue;
                if (r.type == LogRecordType.BEGIN) started.add(r.txnId);
                if (r.type == LogRecordType.COMMIT) committed.add(r.txnId);
                if (r.type == LogRecordType.ABORT) started.remove(r.txnId);
            }
            Set<String> uncommitted = new HashSet<>(started);
            uncommitted.removeAll(committed);

            // REDO phase: replay committed writes
            for (LogRecord r : savedLog) {
                if (r.lsn < lastCheckpointLSN) continue;
                if (r.type == LogRecordType.WRITE && committed.contains(r.txnId)) {
                    wal.state.put(r.key, r.newValue);
                }
            }

            // UNDO phase: rollback uncommitted writes (in reverse)
            List<LogRecord> reversed = new ArrayList<>(savedLog);
            Collections.reverse(reversed);
            for (LogRecord r : reversed) {
                if (r.type == LogRecordType.WRITE && uncommitted.contains(r.txnId)) {
                    if (r.oldValue == null) wal.state.remove(r.key);
                    else wal.state.put(r.key, r.oldValue);
                }
            }

            return wal;
        }

        private void appendLog(LogRecordType type, String txnId, String key, 
                              String oldValue, String newValue) {
            log.add(new LogRecord(nextLSN++, type, txnId, key, oldValue, newValue));
        }

        public String get(String key) { return state.get(key); }
        public Map<String, String> getState() { return Collections.unmodifiableMap(state); }
        public List<LogRecord> getLog() { return Collections.unmodifiableList(log); }
    }

    public static void main(String[] args) {
        System.out.println("=== Write-Ahead Log with Recovery ===\n");

        // Test 1: Normal transaction
        WriteAheadLog wal = new WriteAheadLog();
        String txn1 = wal.beginTransaction();
        wal.write(txn1, "balance", "1000");
        wal.write(txn1, "name", "Alice");
        wal.commit(txn1);
        assert "1000".equals(wal.get("balance"));
        assert "Alice".equals(wal.get("name"));
        System.out.println("PASS: Committed transaction persists state");

        // Test 2: Abort rolls back
        String txn2 = wal.beginTransaction();
        wal.write(txn2, "balance", "9999");
        assert "9999".equals(wal.get("balance")); // visible before abort
        wal.abort(txn2);
        assert "1000".equals(wal.get("balance")); // rolled back
        System.out.println("PASS: Aborted transaction is rolled back");

        // Test 3: Recovery - committed txn survives crash
        wal = new WriteAheadLog();
        String t = wal.beginTransaction();
        wal.write(t, "x", "100");
        wal.commit(t);
        
        // Simulate crash: recover from log
        List<LogRecord> savedLog = new ArrayList<>(wal.getLog());
        WriteAheadLog recovered = WriteAheadLog.recover(savedLog);
        assert "100".equals(recovered.get("x"));
        System.out.println("PASS: Committed data survives crash recovery");

        // Test 4: Recovery - uncommitted txn is rolled back
        wal = new WriteAheadLog();
        t = wal.beginTransaction();
        wal.write(t, "y", "200");
        wal.commit(t);
        
        String uncommitted = wal.beginTransaction();
        wal.write(uncommitted, "y", "EVIL"); // not committed
        wal.write(uncommitted, "z", "GHOST");
        // CRASH! (no commit)

        savedLog = new ArrayList<>(wal.getLog());
        recovered = WriteAheadLog.recover(savedLog);
        assert "200".equals(recovered.get("y")) : "Should rollback to 200, got: " + recovered.get("y");
        assert recovered.get("z") == null : "z should not exist";
        System.out.println("PASS: Uncommitted writes rolled back on recovery");

        // Test 5: Checkpoint reduces recovery scope
        wal = new WriteAheadLog();
        for (int i = 0; i < 100; i++) {
            String tx = wal.beginTransaction();
            wal.write(tx, "counter", String.valueOf(i));
            wal.commit(tx);
        }
        wal.checkpoint();
        String txFinal = wal.beginTransaction();
        wal.write(txFinal, "counter", "999");
        wal.commit(txFinal);

        savedLog = new ArrayList<>(wal.getLog());
        recovered = WriteAheadLog.recover(savedLog);
        assert "999".equals(recovered.get("counter"));
        System.out.println("PASS: Recovery works correctly with checkpoint");

        // Test 6: Print log for inspection
        wal = new WriteAheadLog();
        t = wal.beginTransaction();
        wal.write(t, "account", "500");
        wal.commit(t);
        System.out.println("\nSample WAL entries:");
        for (LogRecord r : wal.getLog()) {
            System.out.println("  " + r);
        }

        System.out.println("\nAll tests passed!");
    }
}
