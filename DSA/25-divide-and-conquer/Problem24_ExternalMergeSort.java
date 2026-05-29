import java.util.*;

/**
 * Problem 24: External Merge Sort
 * 
 * D&C Approach for data too large to fit in memory:
 * - DIVIDE: Split file into chunks that fit in memory
 * - CONQUER: Sort each chunk in memory (using any O(n log n) sort)
 * - COMBINE: K-way merge of sorted chunks using min-heap
 * 
 * Time: O(n log n) with O(n/M) passes where M = memory size
 * Space: O(M) - limited by available memory
 * 
 * Production Analogy:
 * - Database external sort (ORDER BY on large tables)
 * - Hadoop/Spark shuffle phase
 * - Unix sort command for large files
 * - SSTable compaction in LSM-trees (Cassandra, RocksDB)
 */
public class Problem24_ExternalMergeSort {

    // Simulates external merge sort with memory constraint
    public static int[] externalMergeSort(int[] data, int memorySize) {
        int n = data.length;
        if (n <= memorySize) {
            Arrays.sort(data);
            return data;
        }
        
        // Phase 1: Create sorted runs
        List<int[]> sortedRuns = new ArrayList<>();
        for (int i = 0; i < n; i += memorySize) {
            int end = Math.min(i + memorySize, n);
            int[] chunk = Arrays.copyOfRange(data, i, end);
            Arrays.sort(chunk); // In-memory sort
            sortedRuns.add(chunk);
        }
        
        // Phase 2: K-way merge using priority queue
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        // [value, runIndex, indexInRun]
        for (int i = 0; i < sortedRuns.size(); i++) {
            pq.offer(new int[]{sortedRuns.get(i)[0], i, 0});
        }
        
        int[] result = new int[n];
        int idx = 0;
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            result[idx++] = curr[0];
            int runIdx = curr[1], posInRun = curr[2];
            if (posInRun + 1 < sortedRuns.get(runIdx).length) {
                pq.offer(new int[]{sortedRuns.get(runIdx)[posInRun + 1], runIdx, posInRun + 1});
            }
        }
        return result;
    }

    public static void main(String[] args) {
        int[] data1 = {9, 3, 7, 1, 8, 2, 6, 4, 5, 0};
        System.out.println(Arrays.toString(externalMergeSort(data1, 3)));

        int[] data2 = {5, 4, 3, 2, 1};
        System.out.println(Arrays.toString(externalMergeSort(data2, 2)));

        int[] data3 = {1};
        System.out.println(Arrays.toString(externalMergeSort(data3, 1)));

        int[] data4 = {100, 50, 75, 25, 60, 10, 90, 80, 40, 30, 70, 20};
        System.out.println(Arrays.toString(externalMergeSort(data4, 4)));
    }
}
