import java.util.*;

/**
 * Problem 50: Restore IP Addresses (LeetCode 93)
 * 
 * Approach: Backtracking with 4 segments, each 1-3 digits, value 0-255.
 * O(1) time (bounded by 3^4 = 81 combinations max), O(1) space.
 * 
 * Production Analogy: Like parsing and validating IP addresses from raw network packet
 * bytes - must handle leading zeros and range constraints.
 */
public class Problem50_RestoreIPAddresses {

    public static List<String> restoreIpAddresses(String s) {
        List<String> result = new ArrayList<>();
        backtrack(s, 0, new ArrayList<>(), result);
        return result;
    }

    private static void backtrack(String s, int start, List<String> parts, List<String> result) {
        if (parts.size() == 4) {
            if (start == s.length()) result.add(String.join(".", parts));
            return;
        }
        for (int len = 1; len <= 3 && start + len <= s.length(); len++) {
            String part = s.substring(start, start + len);
            if (part.length() > 1 && part.charAt(0) == '0') break; // no leading zeros
            int val = Integer.parseInt(part);
            if (val > 255) break;
            parts.add(part);
            backtrack(s, start + len, parts, result);
            parts.remove(parts.size() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(restoreIpAddresses("25525511135")); // ["255.255.11.135","255.255.111.35"]
        System.out.println(restoreIpAddresses("0000"));         // ["0.0.0.0"]
        System.out.println(restoreIpAddresses("101023"));       // ["1.0.10.23","1.0.102.3","10.1.0.23","10.10.2.3","101.0.2.3"]
        System.out.println(restoreIpAddresses("1111"));         // ["1.1.1.1"]
    }
}
