import java.util.*;

/**
 * Problem 4: Random Pick Index (LeetCode 398)
 * 
 * Given an integer array nums with possible duplicates, randomly return the index
 * of a given target number. Each valid index should have equal probability.
 * 
 * Approach: Reservoir sampling - iterate through array, for each occurrence of target,
 * decide whether to keep current index or replace with new one.
 * 
 * Time: O(n) per pick, Space: O(1) extra (no hashmap needed)
 * Alternative: O(n) space with HashMap<Integer, List<Integer>> for O(1) pick
 */
public class Problem04_RandomPickIndex {

    private int[] nums;
    private Random rand;

    public Problem04_RandomPickIndex(int[] nums) {
        this.nums = nums;
        this.rand = new Random();
    }

    /**
     * Reservoir sampling approach: O(n) time, O(1) space per call
     */
    public int pick(int target) {
        int result = -1;
        int count = 0;
        
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] == target) {
                count++;
                // Replace with probability 1/count
                if (rand.nextInt(count) == 0) {
                    result = i;
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        int[] nums = {1, 2, 3, 3, 3, 4, 5, 3};
        Problem04_RandomPickIndex solution = new Problem04_RandomPickIndex(nums);
        
        System.out.println("LeetCode 398: Random Pick Index");
        System.out.println("Array: [1, 2, 3, 3, 3, 4, 5, 3]");
        System.out.println("Target: 3 (appears at indices 2, 3, 4, 7)\n");
        
        // Verify uniform distribution over indices of target=3
        int trials = 100000;
        Map<Integer, Integer> freq = new HashMap<>();
        for (int t = 0; t < trials; t++) {
            freq.merge(solution.pick(3), 1, Integer::sum);
        }
        
        System.out.println("Distribution of picked indices:");
        for (Map.Entry<Integer, Integer> e : new TreeMap<>(freq).entrySet()) {
            System.out.printf("  Index %d: %.2f%% (expected 25%%)%n", 
                e.getKey(), 100.0 * e.getValue() / trials);
        }
    }
}
