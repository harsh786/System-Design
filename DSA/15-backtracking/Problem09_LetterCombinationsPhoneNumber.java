import java.util.*;

/**
 * Problem 9: Letter Combinations of a Phone Number (LeetCode 17)
 * 
 * Given a string of digits 2-9, return all possible letter combinations.
 * 
 * Search Tree:
 * - Each digit maps to 3-4 letters
 * - At depth i, branch on all letters for digits[i]
 * - Tree depth = digits.length, branching factor = 3 or 4
 * 
 * Pruning Strategy:
 * - No pruning needed; all combinations are valid
 * 
 * Time Complexity: O(4^n * n) where n = digits.length
 * Space Complexity: O(n) recursion depth
 * 
 * Production Analogy:
 * - Auto-complete suggestions: generating all possible word completions from T9 keyboard input.
 */
public class Problem09_LetterCombinationsPhoneNumber {

    private static final String[] MAPPING = {"", "", "abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz"};

    public List<String> letterCombinations(String digits) {
        List<String> result = new ArrayList<>();
        if (digits == null || digits.isEmpty()) return result;
        backtrack(digits, 0, new StringBuilder(), result);
        return result;
    }

    private void backtrack(String digits, int index, StringBuilder current, List<String> result) {
        if (index == digits.length()) {
            result.add(current.toString());
            return;
        }
        String letters = MAPPING[digits.charAt(index) - '0'];
        for (char c : letters.toCharArray()) {
            current.append(c);
            backtrack(digits, index + 1, current, result);
            current.deleteCharAt(current.length() - 1);
        }
    }

    public static void main(String[] args) {
        Problem09_LetterCombinationsPhoneNumber sol = new Problem09_LetterCombinationsPhoneNumber();

        System.out.println(sol.letterCombinations("23"));
        // [ad, ae, af, bd, be, bf, cd, ce, cf]

        System.out.println(sol.letterCombinations(""));   // []
        System.out.println(sol.letterCombinations("2"));  // [a, b, c]
        System.out.println(sol.letterCombinations("79")); // 4*4=16 combinations
    }
}
