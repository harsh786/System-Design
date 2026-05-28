import java.util.*;

/**
 * Problem 30: Group Shifted Strings
 * Group strings that belong to the same shifting sequence.
 * "abc" -> "bcd" -> "xyz" are all in the same group.
 *
 * Approach: Normalize each string by computing differences between consecutive chars.
 * Use the difference tuple as the HashMap key.
 *
 * Time Complexity: O(n * k)
 * Space Complexity: O(n * k)
 *
 * Production Analogy: Like pattern recognition in log messages - grouping logs that
 * differ only by a constant offset (e.g., different timestamps, same pattern).
 */
public class Problem30_GroupShiftedStrings {
    public List<List<String>> groupStrings(String[] strings) {
        Map<String, List<String>> map = new HashMap<>();
        for (String s : strings) {
            StringBuilder key = new StringBuilder();
            for (int i = 1; i < s.length(); i++) {
                int diff = (s.charAt(i) - s.charAt(i-1) + 26) % 26;
                key.append(diff).append(",");
            }
            map.computeIfAbsent(key.toString(), k -> new ArrayList<>()).add(s);
        }
        return new ArrayList<>(map.values());
    }

    public static void main(String[] args) {
        Problem30_GroupShiftedStrings sol = new Problem30_GroupShiftedStrings();
        System.out.println(sol.groupStrings(new String[]{"abc","bcd","acef","xyz","az","ba","a","z"}));
        // [[a,z],[abc,bcd,xyz],[az,ba],[acef]]
    }
}
