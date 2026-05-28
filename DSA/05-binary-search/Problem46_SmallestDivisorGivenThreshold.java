/**
 * Problem 46: Find the Smallest Divisor Given a Threshold
 * 
 * Divide each element by divisor (ceil), sum must be <= threshold. Find smallest divisor.
 * 
 * Approach: Binary search on divisor [1, max(nums)].
 * 
 * Time: O(n * log(max)), Space: O(1)
 * 
 * Production Analogy: Finding minimum batch size for parallel job processing
 * to keep total number of batches within scheduler capacity.
 */
public class Problem46_SmallestDivisorGivenThreshold {
    public static int smallestDivisor(int[] nums, int threshold) {
        int lo = 1, hi = 0;
        for (int n : nums) hi = Math.max(hi, n);
        
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            int sum = 0;
            for (int n : nums) sum += (n + mid - 1) / mid;
            if (sum <= threshold) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(smallestDivisor(new int[]{1,2,5,9}, 6));         // 5
        System.out.println(smallestDivisor(new int[]{44,22,33,11,1}, 5));   // 44
        System.out.println(smallestDivisor(new int[]{21212,10101,12121}, 1000000)); // 1
    }
}
