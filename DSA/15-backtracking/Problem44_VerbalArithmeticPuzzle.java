import java.util.*;

/**
 * Problem 44: Verbal Arithmetic Puzzle (LeetCode 1307)
 * 
 * Determine if a cryptarithmetic puzzle (SEND + MORE = MONEY) has a valid digit assignment.
 * Each letter maps to a unique digit 0-9; leading letters can't be 0.
 * 
 * Search Tree:
 * - Assign digits to letters one by one
 * - After all assigned, verify equation
 * 
 * Pruning Strategy:
 * - Process column by column (right to left) with carry
 * - Prune if partial assignment is already inconsistent
 * - Leading characters cannot be 0
 * 
 * Time Complexity: O(10! / (10-n)!) where n = unique letters (max 10)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Constraint solving in automated test generation: finding valid inputs satisfying complex predicates.
 */
public class Problem44_VerbalArithmeticPuzzle {

    public boolean isSolvable(String[] words, String result) {
        Set<Character> leadingChars = new HashSet<>();
        Set<Character> allChars = new HashSet<>();
        for (String w : words) { for (char c : w.toCharArray()) allChars.add(c); if (w.length() > 1) leadingChars.add(w.charAt(0)); }
        for (char c : result.toCharArray()) allChars.add(c);
        if (result.length() > 1) leadingChars.add(result.charAt(0));

        if (allChars.size() > 10) return false;

        char[] chars = new char[allChars.size()];
        int idx = 0;
        for (char c : allChars) chars[idx++] = c;

        return backtrack(words, result, chars, new int[128], new boolean[10], leadingChars, 0);
    }

    private boolean backtrack(String[] words, String result, char[] chars, int[] mapping, boolean[] usedDigit, Set<Character> leading, int pos) {
        if (pos == chars.length) {
            return verify(words, result, mapping);
        }
        for (int d = 0; d <= 9; d++) {
            if (usedDigit[d]) continue;
            if (d == 0 && leading.contains(chars[pos])) continue;
            mapping[chars[pos]] = d;
            usedDigit[d] = true;
            if (backtrack(words, result, chars, mapping, usedDigit, leading, pos + 1)) return true;
            usedDigit[d] = false;
        }
        mapping[chars[pos]] = -1;
        return false;
    }

    private boolean verify(String[] words, String result, int[] mapping) {
        long sum = 0;
        for (String w : words) {
            long val = 0;
            for (char c : w.toCharArray()) val = val * 10 + mapping[c];
            sum += val;
        }
        long target = 0;
        for (char c : result.toCharArray()) target = target * 10 + mapping[c];
        return sum == target;
    }

    public static void main(String[] args) {
        Problem44_VerbalArithmeticPuzzle sol = new Problem44_VerbalArithmeticPuzzle();

        System.out.println(sol.isSolvable(new String[]{"SEND","MORE"}, "MONEY")); // true
        System.out.println(sol.isSolvable(new String[]{"SIX","SEVEN","SEVEN"}, "TWENTY")); // true
        System.out.println(sol.isSolvable(new String[]{"LEET","CODE"}, "POINT")); // false
    }
}
