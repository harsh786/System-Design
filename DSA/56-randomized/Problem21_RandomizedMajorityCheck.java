import java.util.*;

public class Problem21_RandomizedMajorityCheck {
    // Randomly pick element, check if it's majority - repeat for confidence
    public static int findMajority(int[] nums) {
        Random rand = new Random();
        int trials = 20; // probability of failure = (1/2)^20
        for (int t = 0; t < trials; t++) {
            int candidate = nums[rand.nextInt(nums.length)];
            int count = 0;
            for (int n : nums) if (n == candidate) count++;
            if (count > nums.length / 2) return candidate;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(findMajority(new int[]{2,2,1,1,1,2,2})); // 2
        System.out.println(findMajority(new int[]{1,2,3,4,5})); // -1
    }
}
