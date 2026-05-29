import java.util.*;

/**
 * Problem 26: K-way File Merge
 * 
 * D&C Approach:
 * - DIVIDE: Pair up K sorted files into K/2 pairs
 * - CONQUER: Merge each pair (or use min-heap for direct K-way merge)
 * - COMBINE: Repeat until single merged output
 * 
 * Time: O(N log K) where N = total elements, K = number of files
 * Space: O(K) for heap
 * 
 * Production Analogy:
 * - LSM-tree compaction (merging SSTables in LevelDB/RocksDB)
 * - External sort merge phase
 * - Combining sorted reducer outputs in MapReduce
 * - Kafka log compaction
 */
public class Problem26_KWayFileMerge {

    // Simulates K sorted "files" as sorted arrays
    public static int[] kWayMerge(int[][] files) {
        if (files.length == 0) return new int[0];
        
        // Min-heap: [value, fileIndex, positionInFile]
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        int totalSize = 0;
        
        for (int i = 0; i < files.length; i++) {
            if (files[i].length > 0) {
                pq.offer(new int[]{files[i][0], i, 0});
                totalSize += files[i].length;
            }
        }
        
        int[] result = new int[totalSize];
        int idx = 0;
        
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            result[idx++] = curr[0];
            int fileIdx = curr[1], pos = curr[2];
            if (pos + 1 < files[fileIdx].length) {
                pq.offer(new int[]{files[fileIdx][pos + 1], fileIdx, pos + 1});
            }
        }
        return result;
    }

    // D&C pairwise merge approach
    public static int[] kWayMergeDC(int[][] files) {
        if (files.length == 0) return new int[0];
        return mergeDC(files, 0, files.length - 1);
    }

    private static int[] mergeDC(int[][] files, int lo, int hi) {
        if (lo == hi) return files[lo];
        int mid = lo + (hi - lo) / 2;
        int[] left = mergeDC(files, lo, mid);
        int[] right = mergeDC(files, mid + 1, hi);
        return mergeTwo(left, right);
    }

    private static int[] mergeTwo(int[] a, int[] b) {
        int[] res = new int[a.length + b.length];
        int i = 0, j = 0, k = 0;
        while (i < a.length && j < b.length) {
            if (a[i] <= b[j]) res[k++] = a[i++];
            else res[k++] = b[j++];
        }
        while (i < a.length) res[k++] = a[i++];
        while (j < b.length) res[k++] = b[j++];
        return res;
    }

    public static void main(String[] args) {
        int[][] files = {{1,4,7},{2,5,8},{3,6,9}};
        System.out.println(Arrays.toString(kWayMerge(files)));
        System.out.println(Arrays.toString(kWayMergeDC(files)));

        int[][] files2 = {{1,3,5,7},{2,4,6,8},{0,9,10}};
        System.out.println(Arrays.toString(kWayMerge(files2)));

        int[][] files3 = {{1},{2},{3}};
        System.out.println(Arrays.toString(kWayMerge(files3)));

        int[][] empty = {};
        System.out.println(Arrays.toString(kWayMerge(empty)));
    }
}
