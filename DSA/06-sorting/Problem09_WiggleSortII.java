import java.util.*;

/**
 * Problem 9: Wiggle Sort II
 * 
 * Reorder nums such that nums[0] < nums[1] > nums[2] < nums[3]...
 * 
 * Approach: Sort, then interleave smaller half and larger half from the end to avoid duplicates.
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Load balancing where you interleave heavy and light requests 
 * to prevent burst patterns on downstream services.
 */
public class Problem09_WiggleSortII {
    
    public void wiggleSort(int[] nums) {
        int[] sorted = nums.clone();
        Arrays.sort(sorted);
        
        int n = nums.length;
        int mid = (n - 1) / 2; // end of smaller half
        int end = n - 1;       // end of larger half
        
        // Fill odd indices with larger half (from end), even indices with smaller half (from end)
        for (int i = 0; i < n; i++) {
            if (i % 2 == 0) {
                nums[i] = sorted[mid--];
            } else {
                nums[i] = sorted[end--];
            }
        }
    }
    
    public static void main(String[] args) {
        Problem09_WiggleSortII sol = new Problem09_WiggleSortII();
        
        int[] t1 = {1,5,1,1,6,4};
        sol.wiggleSort(t1);
        System.out.println("Test 1: " + Arrays.toString(t1)); // e.g. [1,6,1,5,1,4]
        
        int[] t2 = {1,3,2,2,3,1};
        sol.wiggleSort(t2);
        System.out.println("Test 2: " + Arrays.toString(t2)); // e.g. [2,3,1,3,1,2]
        
        int[] t3 = {1,1,2,2};
        sol.wiggleSort(t3);
        System.out.println("Test 3: " + Arrays.toString(t3)); // [1,2,1,2]
    }
}
