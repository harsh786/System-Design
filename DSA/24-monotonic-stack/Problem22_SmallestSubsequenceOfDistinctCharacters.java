import java.util.*;

/**
 * Problem 22: Smallest Subsequence of Distinct Characters (LeetCode 1081)
 * 
 * Identical to Problem 21 (Remove Duplicate Letters). Included for completeness.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Same as above - minimum lexicographic unique selection.
 */
public class Problem22_SmallestSubsequenceOfDistinctCharacters {
    
    public String smallestSubsequence(String s) {
        int[] last = new int[26];
        boolean[] used = new boolean[26];
        for (int i = 0; i < s.length(); i++) last[s.charAt(i) - 'a'] = i;
        
        Deque<Character> stack = new ArrayDeque<>();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (used[c - 'a']) continue;
            while (!stack.isEmpty() && stack.peek() > c && last[stack.peek() - 'a'] > i) {
                used[stack.pop() - 'a'] = false;
            }
            stack.push(c);
            used[c - 'a'] = true;
        }
        
        StringBuilder sb = new StringBuilder();
        while (!stack.isEmpty()) sb.append(stack.pollLast());
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem22_SmallestSubsequenceOfDistinctCharacters sol = new Problem22_SmallestSubsequenceOfDistinctCharacters();
        System.out.println(sol.smallestSubsequence("bcabc"));    // "abc"
        System.out.println(sol.smallestSubsequence("cbacdcbc")); // "acdb"
        System.out.println(sol.smallestSubsequence("leetcode")); // "letcod"
    }
}
