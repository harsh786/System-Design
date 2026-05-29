import java.util.*;

/**
 * Problem 49: Dutch National Flag (3-way partition)
 * 
 * Partition array into three sections: elements < pivot, == pivot, > pivot.
 * 
 * Approach: Three pointers (lo, mid, hi). Same as Sort Colors but generalized.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Three-tier routing in load balancers - routing requests to 
 * hot/warm/cold storage tiers based on access frequency threshold.
 */
public class Problem49_DutchNationalFlag3WayPartition {
    
    public void threeWayPartition(int[] nums, int pivot) {
        int lo = 0, mid = 0, hi = nums.length - 1;
        
        while (mid <= hi) {
            if (nums[mid] < pivot) {
                swap(nums, lo++, mid++);
            } else if (nums[mid] == pivot) {
                mid++;
            } else {
                swap(nums, mid, hi--);
            }
        }
    }
    
    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }
    
    // Variant: 3-way quicksort partition returning [lt, gt] boundaries
    public int[] partition3Way(int[] nums, int lo, int hi) {
        int pivot = nums[lo];
        int lt = lo, mid = lo, gt = hi;
        
        while (mid <= gt) {
            if (nums[mid] < pivot) swap(nums, lt++, mid++);
            else if (nums[mid] == pivot) mid++;
            else swap(nums, mid, gt--);
        }
        return new int[]{lt, gt}; // [start of pivot region, end of pivot region]
    }
    
    public static void main(String[] args) {
        Problem49_DutchNationalFlag3WayPartition sol = new Problem49_DutchNationalFlag3WayPartition();
        
        int[] t1 = {3,1,4,1,5,9,2,6,5,3,5};
        sol.threeWayPartition(t1, 5);
        System.out.println("Test 1 (pivot=5): " + Arrays.toString(t1));
        // All <5 first, then 5s, then >5
        
        int[] t2 = {2,0,2,1,1,0};
        sol.threeWayPartition(t2, 1);
        System.out.println("Test 2 (pivot=1): " + Arrays.toString(t2));
        // [0,0,1,1,2,2]
        
        int[] t3 = {5,5,5,5};
        sol.threeWayPartition(t3, 5);
        System.out.println("Test 3 (pivot=5): " + Arrays.toString(t3));
        // [5,5,5,5]
    }
}
