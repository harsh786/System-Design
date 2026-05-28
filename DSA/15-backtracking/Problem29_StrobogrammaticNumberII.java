import java.util.*;

/**
 * Problem 29: Strobogrammatic Number II (LeetCode 247)
 * 
 * Find all strobogrammatic numbers of length n (look same when rotated 180 degrees).
 * Strobogrammatic pairs: (0,0), (1,1), (6,9), (8,8), (9,6)
 * 
 * Search Tree:
 * - Build from outside in: place pairs at positions (i, n-1-i)
 * - Middle character (if n is odd): 0, 1, 8
 * 
 * Pruning Strategy:
 * - Don't place '0' at outermost positions (leading zero)
 * - Only valid pairs can be placed
 * 
 * Time Complexity: O(5^(n/2))
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Generating symmetric/palindromic identifiers for display-invariant systems.
 */
public class Problem29_StrobogrammaticNumberII {

    public List<String> findStrobogrammatic(int n) {
        return helper(n, n);
    }

    private List<String> helper(int n, int totalLen) {
        if (n == 0) return new ArrayList<>(Arrays.asList(""));
        if (n == 1) return new ArrayList<>(Arrays.asList("0", "1", "8"));

        List<String> middles = helper(n - 2, totalLen);
        List<String> result = new ArrayList<>();
        char[][] pairs = {{'0','0'},{'1','1'},{'6','9'},{'8','8'},{'9','6'}};

        for (String mid : middles) {
            for (char[] p : pairs) {
                if (p[0] == '0' && n == totalLen) continue; // no leading zero
                result.add(p[0] + mid + p[1]);
            }
        }
        return result;
    }

    public static void main(String[] args) {
        Problem29_StrobogrammaticNumberII sol = new Problem29_StrobogrammaticNumberII();

        System.out.println(sol.findStrobogrammatic(2)); // [11, 69, 88, 96]
        System.out.println(sol.findStrobogrammatic(1)); // [0, 1, 8]
        System.out.println(sol.findStrobogrammatic(3));
        System.out.println(sol.findStrobogrammatic(4));
    }
}
