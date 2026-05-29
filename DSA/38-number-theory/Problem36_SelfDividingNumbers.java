package numbertheory;

import java.util.*;

/**
 * Problem 36: Self Dividing Numbers (LeetCode 728)
 * 
 * Approach: Check each number: every digit must be non-zero and divide the number.
 * 
 * Time Complexity: O((right-left) * log(right))
 * Space Complexity: O(1) extra
 */
public class Problem36_SelfDividingNumbers {
    
    public List<Integer> selfDividingNumbers(int left, int right) {
        List<Integer> result = new ArrayList<>();
        for (int n = left; n <= right; n++) if (isSelfDividing(n)) result.add(n);
        return result;
    }
    
    private boolean isSelfDividing(int n) {
        int temp = n;
        while (temp > 0) {
            int d = temp % 10;
            if (d == 0 || n % d != 0) return false;
            temp /= 10;
        }
        return true;
    }
    
    public static void main(String[] args) {
        Problem36_SelfDividingNumbers sol = new Problem36_SelfDividingNumbers();
        System.out.println(sol.selfDividingNumbers(1, 22));
    }
}
