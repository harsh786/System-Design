import java.util.*;

public class Problem08_LetterCombinationsOfPhoneNumber {
    private static final String[] MAP = {"","","abc","def","ghi","jkl","mno","pqrs","tuv","wxyz"};

    public List<String> letterCombinations(String digits) {
        List<String> result = new ArrayList<>();
        if (digits.isEmpty()) return result;
        backtrack(result, new StringBuilder(), digits, 0);
        return result;
    }

    private void backtrack(List<String> result, StringBuilder sb, String digits, int idx) {
        if (idx == digits.length()) { result.add(sb.toString()); return; }
        for (char c : MAP[digits.charAt(idx)-'0'].toCharArray()) { sb.append(c); backtrack(result,sb,digits,idx+1); sb.deleteCharAt(sb.length()-1); }
    }

    public static void main(String[] args) { System.out.println(new Problem08_LetterCombinationsOfPhoneNumber().letterCombinations("23")); }
}
