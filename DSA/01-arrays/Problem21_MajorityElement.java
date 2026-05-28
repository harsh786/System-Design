/**
 * Problem 21: Majority Element
 * Find element appearing more than n/2 times.
 * 
 * Production Analogy: Like leader election in distributed systems (Boyer-Moore voting) -
 * the candidate that survives all challenges wins.
 * 
 * O(n) time, O(1) space - Boyer-Moore Voting Algorithm
 */
public class Problem21_MajorityElement {

    public static int majorityElement(int[] nums) {
        int candidate = 0, count = 0;
        for (int n : nums) {
            if (count == 0) candidate = n;
            count += (n == candidate) ? 1 : -1;
        }
        return candidate;
    }

    public static void main(String[] args) {
        System.out.println(majorityElement(new int[]{3,2,3}));         // 3
        System.out.println(majorityElement(new int[]{2,2,1,1,1,2,2})); // 2
        System.out.println(majorityElement(new int[]{1}));              // 1
    }
}
