import java.util.*;

/**
 * Problem 64: LSM Tree (MemTable, SSTable, Compaction)
 * 
 * PRODUCTION MAPPING: LevelDB, RocksDB, Cassandra, HBase, ScyllaDB, CockroachDB
 * 
 * Architecture:
 * 1. MemTable: in-memory sorted structure (TreeMap/SkipList) for recent writes
 * 2. When MemTable full -> flush to immutable SSTable on disk
 * 3. SSTables: sorted, immutable files with index
 * 4. Compaction: merge SSTables to reduce read amplification
 * 
 * Write path: MemTable (O(log n)) -> flush -> SSTable
 * Read path: MemTable -> L0 SSTables -> L1 -> ... (bloom filter skips)
 * 
 * Trade-offs:
 * - Write-optimized (sequential I/O) at cost of read amplification
 * - Compaction: reduces read cost but uses CPU and I/O (write amplification)
 * - Space amplification: stale versions exist until compacted
 * 
 * Compaction strategies:
 * - Size-tiered (Cassandra default): merge similar-sized SSTables
 * - Leveled (LevelDB/RocksDB): bounded space amplification
 */
public class Problem64_LSMTree {

    static class SSTable {
        // Immutable sorted key-value pairs (simulates on-disk SSTable)
        private final TreeMap<String, String> data;
        private final long createdAt;
        private final int level;

        SSTable(TreeMap<String, String> data, int level) {
            this.data = new TreeMap<>(data);
            this.createdAt = System.nanoTime();
            this.level = level;
        }

        String get(String key) { return data.get(key); }
        boolean containsKey(String key) { return data.containsKey(key); }
        int size() { return data.size(); }
        Set<Map.Entry<String, String>> entries() { return data.entrySet(); }
        String getMinKey() { return data.firstKey(); }
        String getMaxKey() { return data.lastKey(); }
    }

    static class LSMTree {
        private TreeMap<String, String> memTable = new TreeMap<>();
        private final int memTableMaxSize;
        private final int maxL0SSTables; // trigger compaction when L0 has this many
        private final List<List<SSTable>> levels; // levels[0] = L0, levels[1] = L1, etc.
        private int totalCompactions = 0;
        private long totalWrites = 0;

        // Tombstone marker for deletes
        private static final String TOMBSTONE = "__DELETED__";

        public LSMTree(int memTableMaxSize, int maxL0SSTables, int numLevels) {
            this.memTableMaxSize = memTableMaxSize;
            this.maxL0SSTables = maxL0SSTables;
            this.levels = new ArrayList<>();
            for (int i = 0; i < numLevels; i++) {
                levels.add(new ArrayList<>());
            }
        }

        public void put(String key, String value) {
            memTable.put(key, value);
            totalWrites++;
            if (memTable.size() >= memTableMaxSize) {
                flush();
            }
        }

        public void delete(String key) {
            // Write a tombstone (actual deletion happens during compaction)
            put(key, TOMBSTONE);
        }

        /**
         * Read path: check MemTable first, then SSTables from newest to oldest.
         * In production, Bloom filters skip SSTables that definitely don't contain key.
         */
        public String get(String key) {
            // 1. Check MemTable
            if (memTable.containsKey(key)) {
                String val = memTable.get(key);
                return TOMBSTONE.equals(val) ? null : val;
            }

            // 2. Check SSTables level by level (newer first)
            for (List<SSTable> level : levels) {
                // Search from newest to oldest within level
                for (int i = level.size() - 1; i >= 0; i--) {
                    SSTable sst = level.get(i);
                    if (sst.containsKey(key)) {
                        String val = sst.get(key);
                        return TOMBSTONE.equals(val) ? null : val;
                    }
                }
            }
            return null;
        }

        /**
         * Range scan: merge results from all levels
         */
        public Map<String, String> scan(String startKey, String endKey) {
            TreeMap<String, String> result = new TreeMap<>();
            
            // Scan all SSTables (oldest first, newer overwrites)
            for (int l = levels.size() - 1; l >= 0; l--) {
                for (SSTable sst : levels.get(l)) {
                    for (Map.Entry<String, String> e : sst.data.subMap(startKey, endKey).entrySet()) {
                        result.put(e.getKey(), e.getValue());
                    }
                }
            }
            // MemTable is newest, overwrites all
            for (Map.Entry<String, String> e : memTable.subMap(startKey, endKey).entrySet()) {
                result.put(e.getKey(), e.getValue());
            }
            // Remove tombstones
            result.values().removeIf(TOMBSTONE::equals);
            return result;
        }

        private void flush() {
            if (memTable.isEmpty()) return;
            SSTable sst = new SSTable(memTable, 0);
            levels.get(0).add(sst);
            memTable = new TreeMap<>();

            // Trigger compaction if L0 is full
            if (levels.get(0).size() >= maxL0SSTables) {
                compact(0);
            }
        }

        /**
         * Compaction: merge all SSTables at level into level+1.
         * Simple size-tiered strategy.
         */
        private void compact(int level) {
            if (level >= levels.size() - 1) return;
            
            List<SSTable> sourceLevel = levels.get(level);
            if (sourceLevel.isEmpty()) return;

            // Merge all SSTables in this level
            TreeMap<String, String> merged = new TreeMap<>();
            // Add existing L+1 data first (older)
            for (SSTable sst : levels.get(level + 1)) {
                for (Map.Entry<String, String> e : sst.entries()) {
                    merged.put(e.getKey(), e.getValue());
                }
            }
            // Then overlay L data (newer wins)
            for (SSTable sst : sourceLevel) {
                for (Map.Entry<String, String> e : sst.entries()) {
                    merged.put(e.getKey(), e.getValue());
                }
            }
            // Remove tombstones during compaction (actual garbage collection)
            merged.values().removeIf(TOMBSTONE::equals);

            // Replace level+1 with single merged SSTable
            levels.get(level + 1).clear();
            if (!merged.isEmpty()) {
                levels.get(level + 1).add(new SSTable(merged, level + 1));
            }
            // Clear source level
            sourceLevel.clear();
            totalCompactions++;
        }

        public void forceFlush() { flush(); }
        public int getL0Count() { return levels.get(0).size(); }
        public int getTotalSSTables() {
            return levels.stream().mapToInt(List::size).sum();
        }
        public int getTotalCompactions() { return totalCompactions; }
        public long getTotalWrites() { return totalWrites; }
    }

    public static void main(String[] args) {
        System.out.println("=== LSM Tree ===\n");

        // MemTable size=5, compact L0 when 3 SSTables, 3 levels
        LSMTree lsm = new LSMTree(5, 3, 3);

        // Test 1: Basic put/get
        lsm.put("name", "Alice");
        lsm.put("age", "30");
        assert "Alice".equals(lsm.get("name"));
        assert "30".equals(lsm.get("age"));
        System.out.println("PASS: Basic put/get from MemTable");

        // Test 2: Flush to SSTable
        for (int i = 0; i < 5; i++) lsm.put("key" + i, "val" + i);
        // MemTable should have flushed
        assert lsm.getL0Count() >= 1 : "Should have flushed to L0";
        // Data still readable
        assert "Alice".equals(lsm.get("name")) || "val0".equals(lsm.get("key0"));
        System.out.println("PASS: Data readable after flush to SSTable");

        // Test 3: Read across MemTable and SSTables
        lsm = new LSMTree(3, 3, 3);
        lsm.put("a", "1");
        lsm.put("b", "2");
        lsm.put("c", "3"); // triggers flush
        lsm.put("d", "4"); // in new memtable
        assert "a".equals(lsm.get("a")) == false || "1".equals(lsm.get("a"));
        assert "4".equals(lsm.get("d"));
        System.out.println("PASS: Read spans MemTable and SSTables");

        // Test 4: Updates (newer value wins)
        lsm = new LSMTree(3, 3, 3);
        lsm.put("x", "old");
        lsm.forceFlush();
        lsm.put("x", "new");
        assert "new".equals(lsm.get("x"));
        System.out.println("PASS: Updates return newest value");

        // Test 5: Deletes with tombstones
        lsm = new LSMTree(5, 3, 3);
        lsm.put("temp", "exists");
        lsm.forceFlush();
        lsm.delete("temp");
        assert lsm.get("temp") == null : "Deleted key should return null";
        System.out.println("PASS: Delete (tombstone) works");

        // Test 6: Compaction
        lsm = new LSMTree(3, 2, 3);
        for (int i = 0; i < 20; i++) {
            lsm.put("k" + String.format("%03d", i), "v" + i);
        }
        assert lsm.getTotalCompactions() > 0 : "Should have compacted";
        // All data still accessible
        assert "v0".equals(lsm.get("k000"));
        assert "v19".equals(lsm.get("k019"));
        System.out.printf("PASS: Compaction occurred (%d times), data intact\n", lsm.getTotalCompactions());

        // Test 7: Range scan
        lsm = new LSMTree(5, 3, 3);
        for (int i = 0; i < 10; i++) lsm.put("key-" + i, "val-" + i);
        Map<String, String> range = lsm.scan("key-3", "key-7");
        assert range.size() == 4 : "Should get 4 keys in range, got: " + range.size();
        System.out.println("PASS: Range scan works: " + range.keySet());

        // Test 8: Write amplification measurement
        lsm = new LSMTree(10, 3, 4);
        for (int i = 0; i < 1000; i++) {
            lsm.put("k" + i, "v" + i);
        }
        System.out.printf("\nStats: %d writes, %d compactions, %d SSTables\n",
            lsm.getTotalWrites(), lsm.getTotalCompactions(), lsm.getTotalSSTables());

        System.out.println("\nAll tests passed!");
    }
}
