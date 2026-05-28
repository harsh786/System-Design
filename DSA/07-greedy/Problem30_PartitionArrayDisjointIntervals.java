/**
 * Problem 30: Partition Array into Disjoint Intervals (LeetCode 915)
 *
 * Greedy Choice: Track max of left partition. If current element < left max, extend left.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Finding split point in time-series data where all past values <= all future values.
 */
public class Problem30_PartitionArrayDisjointIntervals {
    
    public static int partitionDisjoint(int[] nums) {
        int leftMax = nums[0], globalMax = nums[0], partitionIdx = 0;
        for (int i = 1; i < nums.length; i++) {
            if (nums[i] < leftMax) {
                leftMax = globalMax;
                partitionIdx = i;
            } else {
                globalMax = Math.max(globalMax, nums[i]);
            }
        }
        return partitionIdx + 1;
    }
    
    public static void main(String[] args) {
        System.out.println(partitionDisjoint(new int[]{5,0,3,8,6}));   // 3
        System.out.println(partitionDisjoint(new int[]{1,1,1,0,6,12})); // 4
        System.out.println(partitionDisjoint(new int[]{1,2,3,4,5}));    // 1
    }
}
