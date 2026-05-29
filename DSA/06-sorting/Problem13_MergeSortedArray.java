import java.util.*;

/**
 * Problem 13: Merge Sorted Array
 * 
 * Merge nums2 into nums1 (which has enough space). Both sorted.
 * 
 * Approach: Three pointers from the end to avoid overwriting.
 * Time Complexity: O(m + n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Merging sorted WAL (Write-Ahead Log) segments during LSM-tree compaction
 * in databases like RocksDB/LevelDB.
 */
public class Problem13_MergeSortedArray {
    
    public void merge(int[] nums1, int m, int[] nums2, int n) {
        int i = m - 1, j = n - 1, k = m + n - 1;
        while (j >= 0) {
            if (i >= 0 && nums1[i] > nums2[j]) {
                nums1[k--] = nums1[i--];
            } else {
                nums1[k--] = nums2[j--];
            }
        }
    }
    
    public static void main(String[] args) {
        Problem13_MergeSortedArray sol = new Problem13_MergeSortedArray();
        
        int[] t1 = {1,2,3,0,0,0};
        sol.merge(t1, 3, new int[]{2,5,6}, 3);
        System.out.println("Test 1: " + Arrays.toString(t1)); // [1,2,2,3,5,6]
        
        int[] t2 = {1};
        sol.merge(t2, 1, new int[]{}, 0);
        System.out.println("Test 2: " + Arrays.toString(t2)); // [1]
        
        int[] t3 = {0};
        sol.merge(t3, 0, new int[]{1}, 1);
        System.out.println("Test 3: " + Arrays.toString(t3)); // [1]
        
        int[] t4 = {4,5,6,0,0,0};
        sol.merge(t4, 3, new int[]{1,2,3}, 3);
        System.out.println("Test 4: " + Arrays.toString(t4)); // [1,2,3,4,5,6]
    }
}
