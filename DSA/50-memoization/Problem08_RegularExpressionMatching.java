import java.util.*;

public class Problem08_RegularExpressionMatching {
    private Map<String, Boolean> memo = new HashMap<>();

    public boolean isMatch(String s, String p) {
        String key = s + "," + p;
        if (memo.containsKey(key)) return memo.get(key);
        if (p.isEmpty()) { memo.put(key, s.isEmpty()); return s.isEmpty(); }
        boolean firstMatch = !s.isEmpty() && (s.charAt(0) == p.charAt(0) || p.charAt(0) == '.');
        boolean result;
        if (p.length() >= 2 && p.charAt(1) == '*') {
            result = isMatch(s, p.substring(2)) || (firstMatch && isMatch(s.substring(1), p));
        } else {
            result = firstMatch && isMatch(s.substring(1), p.substring(1));
        }
        memo.put(key, result);
        return result;
    }

    public static void main(String[] args) {
        Problem08_RegularExpressionMatching sol = new Problem08_RegularExpressionMatching();
        System.out.println("isMatch('aab','c*a*b'): " + sol.isMatch("aab", "c*a*b")); // true
    }
}
