import java.util.*;

/**
 * Problem 25: The K-th Lexicographical Happy String (LeetCode 1415)
 * 
 * A happy string has only 'a','b','c' and no two adjacent characters are the same.
 * Return the k-th happy string of length n in lexicographical order.
 * 
 * Search Tree:
 * - At each position, try 'a','b','c' (in order) if different from previous
 * - First valid string of length n found decrements k; when k=0, we have answer
 * 
 * Pruning Strategy:
 * - Only try characters different from last character (2 choices after first)
 * - Generate in lexicographic order so k-th is found naturally
 * 
 * Time Complexity: O(k * n) since we generate strings in order until k-th
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Generating valid sequential IDs with constraints (no consecutive repeated characters).
 */
public class Problem25_KthLexicographicalHappyString {

    private int count;
    private String result;

    public String getHappyString(int n, int k) {
        count = k;
        result = "";
        backtrack(n, new StringBuilder());
        return result;
    }

    private void backtrack(int n, StringBuilder sb) {
        if (!result.isEmpty()) return; // already found
        if (sb.length() == n) {
            count--;
            if (count == 0) result = sb.toString();
            return;
        }
        for (char c = 'a'; c <= 'c'; c++) {
            if (sb.length() > 0 && sb.charAt(sb.length() - 1) == c) continue;
            sb.append(c);
            backtrack(n, sb);
            sb.deleteCharAt(sb.length() - 1);
        }
    }

    public static void main(String[] args) {
        Problem25_KthLexicographicalHappyString sol = new Problem25_KthLexicographicalHappyString();

        System.out.println(sol.getHappyString(1, 3)); // "c"
        System.out.println(sol.getHappyString(1, 4)); // ""
        System.out.println(sol.getHappyString(3, 9)); // "cab"
    }
}
