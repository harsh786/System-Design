import java.util.*;

/**
 * Problem 16: Restore IP Addresses (LeetCode 93)
 * 
 * Given a string of digits, return all possible valid IP addresses.
 * 
 * Search Tree:
 * - Split string into exactly 4 parts, each 1-3 digits, value 0-255, no leading zeros
 * 
 * Pruning Strategy:
 * - If remaining digits > 3 * remaining parts or < remaining parts, prune
 * - If segment value > 255 or has leading zero (length > 1), prune
 * 
 * Time Complexity: O(3^4) = O(81) since max 3 choices at each of 4 levels
 * Space Complexity: O(1) constant segments
 * 
 * Production Analogy:
 * - Parsing/validating structured network addresses from raw byte streams.
 */
public class Problem16_RestoreIPAddresses {

    public List<String> restoreIpAddresses(String s) {
        List<String> result = new ArrayList<>();
        backtrack(s, 0, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(String s, int start, List<String> segments, List<String> result) {
        if (segments.size() == 4) {
            if (start == s.length()) result.add(String.join(".", segments));
            return;
        }
        int remaining = s.length() - start;
        int need = 4 - segments.size();
        if (remaining < need || remaining > need * 3) return; // pruning

        for (int len = 1; len <= 3 && start + len <= s.length(); len++) {
            String seg = s.substring(start, start + len);
            if (seg.length() > 1 && seg.charAt(0) == '0') break; // leading zero
            if (Integer.parseInt(seg) > 255) break;
            segments.add(seg);
            backtrack(s, start + len, segments, result);
            segments.remove(segments.size() - 1);
        }
    }

    public static void main(String[] args) {
        Problem16_RestoreIPAddresses sol = new Problem16_RestoreIPAddresses();

        System.out.println(sol.restoreIpAddresses("25525511135"));
        // [255.255.11.135, 255.255.111.35]

        System.out.println(sol.restoreIpAddresses("0000")); // [0.0.0.0]
        System.out.println(sol.restoreIpAddresses("101023"));
        System.out.println(sol.restoreIpAddresses("1111111111111")); // too long -> []
    }
}
