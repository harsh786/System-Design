import java.util.*;

/**
 * Problem 49: Letter Combinations of a Phone Number (LeetCode 17)
 * 
 * Approach: Backtracking. O(4^n) time, O(n) space.
 * 
 * Production Analogy: Like generating all possible configuration combinations
 * from a set of multi-valued feature flags.
 */
public class Problem49_LetterCombinationsPhoneNumber {

    private static final String[] MAPPING = {"","","abc","def","ghi","jkl","mno","pqrs","tuv","wxyz"};

    public static List<String> letterCombinations(String digits) {
        List<String> result = new ArrayList<>();
        if (digits.isEmpty()) return result;
        backtrack(digits, 0, new StringBuilder(), result);
        return result;
    }

    private static void backtrack(String digits, int idx, StringBuilder sb, List<String> result) {
        if (idx == digits.length()) { result.add(sb.toString()); return; }
        for (char c : MAPPING[digits.charAt(idx) - '0'].toCharArray()) {
            sb.append(c);
            backtrack(digits, idx + 1, sb, result);
            sb.deleteCharAt(sb.length() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(letterCombinations("23")); // [ad,ae,af,bd,be,bf,cd,ce,cf]
        System.out.println(letterCombinations(""));   // []
        System.out.println(letterCombinations("2"));  // [a,b,c]
    }
}
