import java.util.*;

public class Problem40_LetterCombinationsOfPhoneNumber {
    static String[] mapping = {"", "", "abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz"};
    public static List<String> letterCombinations(String digits) {
        List<String> res = new ArrayList<>();
        if (digits.isEmpty()) return res;
        backtrack(res, new StringBuilder(), digits, 0);
        return res;
    }
    static void backtrack(List<String> res, StringBuilder sb, String digits, int idx) {
        if (idx == digits.length()) { res.add(sb.toString()); return; }
        for (char c : mapping[digits.charAt(idx) - '0'].toCharArray()) {
            sb.append(c); backtrack(res, sb, digits, idx + 1); sb.deleteCharAt(sb.length() - 1);
        }
    }
    public static void main(String[] args) {
        System.out.println(letterCombinations("23"));
    }
}
