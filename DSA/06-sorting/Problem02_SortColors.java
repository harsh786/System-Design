import java.util.*;

/**
 * Problem 2: Sort Colors (Dutch National Flag)
 * 
 * Given an array with n objects colored red(0), white(1), blue(2), sort in-place.
 * 
 * Approach: Three-pointer technique (lo, mid, hi). 
 * - 0s go to front (swap with lo), 2s go to back (swap with hi), 1s stay in middle.
 * Time Complexity: O(n) single pass
 * Space Complexity: O(1) in-place
 * 
 * Production Analogy: Priority queue triage in incident management - P0/P1/P2 severity 
 * routing in a single pass through alert queue.
 */
public class Problem02_SortColors {
    
    public void sortColors(int[] nums) {
        int lo = 0, mid = 0, hi = nums.length - 1;
        
        while (mid <= hi) {
            if (nums[mid] == 0) {
                swap(nums, lo++, mid++);
            } else if (nums[mid] == 1) {
                mid++;
            } else {
                swap(nums, mid, hi--);
            }
        }
    }
    
    private void swap(int[] nums, int i, int j) {
        int tmp = nums[i]; nums[i] = nums[j]; nums[j] = tmp;
    }
    
    public static void main(String[] args) {
        Problem02_SortColors sol = new Problem02_SortColors();
        
        int[] t1 = {2,0,2,1,1,0};
        sol.sortColors(t1);
        System.out.println("Test 1: " + Arrays.toString(t1)); // [0,0,1,1,2,2]
        
        int[] t2 = {2,0,1};
        sol.sortColors(t2);
        System.out.println("Test 2: " + Arrays.toString(t2)); // [0,1,2]
        
        int[] t3 = {0};
        sol.sortColors(t3);
        System.out.println("Test 3: " + Arrays.toString(t3)); // [0]
        
        int[] t4 = {1,1,1};
        sol.sortColors(t4);
        System.out.println("Test 4: " + Arrays.toString(t4)); // [1,1,1]
        
        int[] t5 = {2,2,2,0,0,0};
        sol.sortColors(t5);
        System.out.println("Test 5: " + Arrays.toString(t5)); // [0,0,0,2,2,2]
    }
}
