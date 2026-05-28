import java.util.*;

/**
 * Problem 31: Letter Case Permutation (LeetCode 784)
 * 
 * Given a string, transform every letter to lowercase or uppercase to create all variants.
 * 
 * Search Tree:
 * - At each character: if letter, branch into lower and upper; if digit, just keep
 * 
 * Pruning Strategy:
 * - Digits have only one option (no branching needed)
 * 
 * Time Complexity: O(2^L * n) where L = number of letters
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Case-insensitive search: generating all case variants for matching against case-sensitive systems.
 */
public class Problem31_LetterCasePermutation {

    public List<String> letterCasePermutation(String s) {
        List<String> result = new ArrayList<>();
        backtrack(s.toCharArray(), 0, result);
        return result;
    }

    private void backtrack(char[] chars, int idx, List<String> result) {
        if (idx == chars.length) {
            result.add(new String(chars));
            return;
        }
        if (Character.isLetter(chars[idx])) {
            chars[idx] = Character.toLowerCase(chars[idx]);
            backtrack(chars, idx + 1, result);
            chars[idx] = Character.toUpperCase(chars[idx]);
            backtrack(chars, idx + 1, result);
        } else {
            backtrack(chars, idx + 1, result);
        }
    }

    public static void main(String[] args) {
        Problem31_LetterCasePermutation sol = new Problem31_LetterCasePermutation();

        System.out.println(sol.letterCasePermutation("a1b2")); // [a1b2, a1B2, A1b2, A1B2]
        System.out.println(sol.letterCasePermutation("3z4"));  // [3z4, 3Z4]
        System.out.println(sol.letterCasePermutation("12345")); // [12345]
    }
}
