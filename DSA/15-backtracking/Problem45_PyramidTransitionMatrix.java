import java.util.*;

/**
 * Problem 45: Pyramid Transition Matrix (LeetCode 756)
 * 
 * Given a bottom row and allowed triples (two adjacent chars produce a char above),
 * determine if we can build a full pyramid.
 * 
 * Search Tree:
 * - For each pair in current row, try all allowed characters for the row above
 * - Build next row left to right, then recurse on next row
 * 
 * Pruning Strategy:
 * - If any pair has no allowed character, prune immediately
 * - Memoize on row state (optional)
 * 
 * Time Complexity: O(7^(n*(n-1)/2)) worst case where n = bottom length
 * Space Complexity: O(n^2)
 * 
 * Production Analogy:
 * - Hierarchical aggregation: determining if bottom-level metrics can be rolled up to a valid top-level summary.
 */
public class Problem45_PyramidTransitionMatrix {

    public boolean pyramidTransition(String bottom, List<String> allowed) {
        Map<String, List<Character>> map = new HashMap<>();
        for (String s : allowed) {
            String key = s.substring(0, 2);
            map.computeIfAbsent(key, k -> new ArrayList<>()).add(s.charAt(2));
        }
        return build(bottom, map);
    }

    private boolean build(String row, Map<String, List<Character>> map) {
        if (row.length() == 1) return true;
        return buildNext(row, 0, new StringBuilder(), map);
    }

    private boolean buildNext(String row, int idx, StringBuilder next, Map<String, List<Character>> map) {
        if (idx == row.length() - 1) {
            return build(next.toString(), map);
        }
        String key = row.substring(idx, idx + 2);
        List<Character> options = map.getOrDefault(key, Collections.emptyList());
        for (char c : options) {
            next.append(c);
            if (buildNext(row, idx + 1, next, map)) return true;
            next.deleteCharAt(next.length() - 1);
        }
        return false;
    }

    public static void main(String[] args) {
        Problem45_PyramidTransitionMatrix sol = new Problem45_PyramidTransitionMatrix();

        System.out.println(sol.pyramidTransition("BCD",
            Arrays.asList("BCC","CDE","CEA","FFF"))); // true

        System.out.println(sol.pyramidTransition("AABA",
            Arrays.asList("AAA","AAB","ABA","ABB","BAC"))); // false
    }
}
