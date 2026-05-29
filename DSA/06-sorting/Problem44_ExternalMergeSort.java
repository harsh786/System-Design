import java.util.*;

/**
 * Problem 44: External Merge Sort
 * 
 * Sort data that doesn't fit in memory by dividing into chunks, sorting each, 
 * then merging sorted chunks using a min-heap.
 * 
 * Approach: Simulate external sort - split into sorted runs, k-way merge with priority queue.
 * Time Complexity: O(n log n) overall, O(n log k) for merge phase
 * Space Complexity: O(k) for merge (k = number of runs)
 * 
 * Production Analogy: Database external sort for large tables (ORDER BY on billion rows),
 * Hadoop MapReduce shuffle phase, or sorting terabyte-scale log files.
 */
public class Problem44_ExternalMergeSort {
    
    /**
     * Simulates external merge sort:
     * 1. Split array into chunks that fit in "memory" (chunkSize)
     * 2. Sort each chunk independently
     * 3. K-way merge all sorted chunks
     */
    public int[] externalMergeSort(int[] data, int chunkSize) {
        int n = data.length;
        
        // Phase 1: Create sorted runs
        List<int[]> sortedRuns = new ArrayList<>();
        for (int i = 0; i < n; i += chunkSize) {
            int end = Math.min(i + chunkSize, n);
            int[] chunk = Arrays.copyOfRange(data, i, end);
            Arrays.sort(chunk); // Sort in "memory"
            sortedRuns.add(chunk);
        }
        
        // Phase 2: K-way merge using min-heap
        // PQ entry: [value, runIndex, positionInRun]
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        for (int i = 0; i < sortedRuns.size(); i++) {
            pq.offer(new int[]{sortedRuns.get(i)[0], i, 0});
        }
        
        int[] result = new int[n];
        int idx = 0;
        
        while (!pq.isEmpty()) {
            int[] top = pq.poll();
            result[idx++] = top[0];
            int runIdx = top[1], pos = top[2] + 1;
            if (pos < sortedRuns.get(runIdx).length) {
                pq.offer(new int[]{sortedRuns.get(runIdx)[pos], runIdx, pos});
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem44_ExternalMergeSort sol = new Problem44_ExternalMergeSort();
        
        int[] t1 = {38, 27, 43, 3, 9, 82, 10, 1, 55, 44, 23, 7};
        System.out.println("Test 1 (chunk=3): " + Arrays.toString(sol.externalMergeSort(t1, 3)));
        // [1,3,7,9,10,23,27,38,43,44,55,82]
        
        int[] t2 = {5, 3, 1, 4, 2};
        System.out.println("Test 2 (chunk=2): " + Arrays.toString(sol.externalMergeSort(t2, 2)));
        // [1,2,3,4,5]
        
        int[] t3 = {1};
        System.out.println("Test 3 (chunk=1): " + Arrays.toString(sol.externalMergeSort(t3, 1)));
        // [1]
    }
}
