import java.util.*;

/**
 * Problem 32: Brace Expansion (LeetCode 1087)
 * 
 * Given a string like "{a,b}c{d,e}f", expand all combinations sorted lexicographically.
 * 
 * Search Tree:
 * - Parse groups: each {a,b,c} is a choice point, plain chars are fixed
 * - At each group, branch on each option
 * 
 * Pruning Strategy:
 * - Sort options within each group for lexicographic output
 * - No other pruning needed
 * 
 * Time Complexity: O(product of group sizes * string length)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Template expansion in deployment configs (e.g., expanding {dev,staging,prod} in URLs).
 */
public class Problem32_BraceExpansion {

    public String[] expand(String s) {
        List<List<Character>> groups = new ArrayList<>();
        int i = 0;
        while (i < s.length()) {
            List<Character> group = new ArrayList<>();
            if (s.charAt(i) == '{') {
                i++;
                while (s.charAt(i) != '}') {
                    if (s.charAt(i) != ',') group.add(s.charAt(i));
                    i++;
                }
                i++; // skip '}'
            } else {
                group.add(s.charAt(i));
                i++;
            }
            Collections.sort(group);
            groups.add(group);
        }
        List<String> result = new ArrayList<>();
        backtrack(groups, 0, new StringBuilder(), result);
        return result.toArray(new String[0]);
    }

    private void backtrack(List<List<Character>> groups, int idx, StringBuilder sb, List<String> result) {
        if (idx == groups.size()) {
            result.add(sb.toString());
            return;
        }
        for (char c : groups.get(idx)) {
            sb.append(c);
            backtrack(groups, idx + 1, sb, result);
            sb.deleteCharAt(sb.length() - 1);
        }
    }

    public static void main(String[] args) {
        Problem32_BraceExpansion sol = new Problem32_BraceExpansion();

        System.out.println(Arrays.toString(sol.expand("{a,b}c{d,e}f")));
        // [acdf, acef, bcdf, bcef]

        System.out.println(Arrays.toString(sol.expand("abcd")));
        // [abcd]

        System.out.println(Arrays.toString(sol.expand("{a,b}{c,d}")));
        // [ac, ad, bc, bd]
    }
}
