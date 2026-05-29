import java.util.*;

/**
 * Problem 26: Radix Sort Implementation
 * 
 * Sort integers by processing digits from least significant to most significant.
 * 
 * Approach: Use counting sort as subroutine for each digit position.
 * Time Complexity: O(d * (n + k)) where d=digits, k=base (10)
 * Space Complexity: O(n + k)
 * Stability: Stable
 * 
 * Production Analogy: Sorting IP addresses, phone numbers, or fixed-length record keys
 * in database index construction.
 */
public class Problem26_RadixSortImplementation {
    
    public int[] radixSort(int[] nums) {
        if (nums.length == 0) return nums;
        
        // Handle negatives by separating them
        int max = 0;
        for (int n : nums) max = Math.max(max, Math.abs(n));
        
        // Sort by each digit
        for (int exp = 1; max / exp > 0; exp *= 10) {
            countingSortByDigit(nums, exp);
        }
        
        // Handle negatives: partition negatives and positives
        // For simplicity, assuming non-negative here
        return nums;
    }
    
    private void countingSortByDigit(int[] nums, int exp) {
        int n = nums.length;
        int[] output = new int[n];
        int[] count = new int[10];
        
        for (int num : nums) count[(num / exp) % 10]++;
        for (int i = 1; i < 10; i++) count[i] += count[i - 1];
        
        for (int i = n - 1; i >= 0; i--) {
            int digit = (nums[i] / exp) % 10;
            output[--count[digit]] = nums[i];
        }
        System.arraycopy(output, 0, nums, 0, n);
    }
    
    // Full version handling negatives
    public int[] radixSortFull(int[] nums) {
        List<Integer> neg = new ArrayList<>(), pos = new ArrayList<>();
        for (int n : nums) {
            if (n < 0) neg.add(-n);
            else pos.add(n);
        }
        
        int[] negArr = neg.stream().mapToInt(Integer::intValue).toArray();
        int[] posArr = pos.stream().mapToInt(Integer::intValue).toArray();
        
        if (negArr.length > 0) radixSort(negArr);
        if (posArr.length > 0) radixSort(posArr);
        
        int idx = 0;
        for (int i = negArr.length - 1; i >= 0; i--) nums[idx++] = -negArr[i];
        for (int i = 0; i < posArr.length; i++) nums[idx++] = posArr[i];
        return nums;
    }
    
    public static void main(String[] args) {
        Problem26_RadixSortImplementation sol = new Problem26_RadixSortImplementation();
        
        System.out.println("Test 1: " + Arrays.toString(sol.radixSort(new int[]{170,45,75,90,802,24,2,66}))); 
        // [2,24,45,66,75,90,170,802]
        
        System.out.println("Test 2: " + Arrays.toString(sol.radixSortFull(new int[]{-3,5,-1,0,2,-2})));
        // [-3,-2,-1,0,2,5]
        
        System.out.println("Test 3: " + Arrays.toString(sol.radixSort(new int[]{1}))); // [1]
    }
}
