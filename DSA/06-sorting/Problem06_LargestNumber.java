import java.util.*;

/**
 * Problem 6: Largest Number
 * 
 * Given a list of non-negative integers, arrange them to form the largest number.
 * 
 * Approach: Custom comparator - compare concatenations: (a+b) vs (b+a).
 * Time Complexity: O(n log n * k) where k is average digit length
 * Space Complexity: O(n)
 * 
 * Production Analogy: Version string comparison in package managers, or constructing 
 * optimal composite keys for database indexing.
 */
public class Problem06_LargestNumber {
    
    public String largestNumber(int[] nums) {
        String[] strs = new String[nums.length];
        for (int i = 0; i < nums.length; i++) strs[i] = String.valueOf(nums[i]);
        
        Arrays.sort(strs, (a, b) -> (b + a).compareTo(a + b));
        
        if (strs[0].equals("0")) return "0";
        
        StringBuilder sb = new StringBuilder();
        for (String s : strs) sb.append(s);
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem06_LargestNumber sol = new Problem06_LargestNumber();
        
        System.out.println("Test 1: " + sol.largestNumber(new int[]{10,2})); // "210"
        System.out.println("Test 2: " + sol.largestNumber(new int[]{3,30,34,5,9})); // "9534330"
        System.out.println("Test 3: " + sol.largestNumber(new int[]{0,0})); // "0"
        System.out.println("Test 4: " + sol.largestNumber(new int[]{1})); // "1"
        System.out.println("Test 5: " + sol.largestNumber(new int[]{999999998,999999997,999999999})); // "999999999999999998999999997"
    }
}
