import java.util.*;

public class Problem24_RepeatedSubstringPattern {
    public boolean repeatedSubstringPattern(String s) {
        int n = s.length();
        for (int len = 1; len <= n / 2; len++) {
            if (n % len != 0) continue;
            String pattern = s.substring(0, len);
            int hash = pattern.hashCode();
            boolean valid = true;
            for (int i = len; i < n; i += len) {
                if (s.substring(i, i + len).hashCode() != hash || !s.substring(i, i+len).equals(pattern)) { valid = false; break; }
            }
            if (valid) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        Problem24_RepeatedSubstringPattern sol = new Problem24_RepeatedSubstringPattern();
        System.out.println(sol.repeatedSubstringPattern("abab")); // true
        System.out.println(sol.repeatedSubstringPattern("abc")); // false
    }
}
