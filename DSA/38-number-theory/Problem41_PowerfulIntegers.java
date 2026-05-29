package numbertheory;

import java.util.*;

/**
 * Problem 41: Powerful Integers (LeetCode 970)
 * 
 * Approach: Generate all x^i + y^j <= bound.
 * 
 * Time Complexity: O(log(bound)^2)
 * Space Complexity: O(result size)
 */
public class Problem41_PowerfulIntegers {
    
    public List<Integer> powerfulIntegers(int x, int y, int bound) {
        Set<Integer> set = new HashSet<>();
        for (int a = 1; a <= bound; a *= x) {
            for (int b = 1; a + b <= bound; b *= y) {
                set.add(a + b);
                if (y == 1) break;
            }
            if (x == 1) break;
        }
        return new ArrayList<>(set);
    }
    
    public static void main(String[] args) {
        Problem41_PowerfulIntegers sol = new Problem41_PowerfulIntegers();
        System.out.println(sol.powerfulIntegers(2, 3, 10)); // [2,3,4,5,7,9,10]
    }
}
