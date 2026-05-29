import java.util.*;

/**
 * Problem: Alien Dictionary with Invalid Cases
 * Handle all edge cases: prefix conflicts, cycles, disconnected chars.
 *
 * Approach: Same as alien dictionary but with explicit invalid case handling
 *
 * Time Complexity: O(C)
 * Space Complexity: O(1)
 *
 * Production Analogy: Robust config validation that provides clear error messages.
 */
public class Problem25_AlienDictionaryWithInvalidCases {

    public String alienOrder(String[] words) {
        if (words == null || words.length == 0) return "";

        Map<Character, Set<Character>> graph = new HashMap<>();
        Map<Character, Integer> inDeg = new HashMap<>();

        for (String w : words)
            for (char c : w.toCharArray()) { graph.putIfAbsent(c, new HashSet<>()); inDeg.putIfAbsent(c, 0); }

        for (int i = 0; i < words.length - 1; i++) {
            String w1 = words[i], w2 = words[i + 1];
            if (w1.length() > w2.length() && w1.startsWith(w2)) return ""; // Invalid prefix
            int len = Math.min(w1.length(), w2.length());
            for (int j = 0; j < len; j++) {
                char a = w1.charAt(j), b = w2.charAt(j);
                if (a != b) {
                    if (graph.get(a).add(b)) inDeg.merge(b, 1, Integer::sum);
                    break;
                }
            }
        }

        Queue<Character> q = new PriorityQueue<>(); // lexicographic for determinism
        for (char c : inDeg.keySet()) if (inDeg.get(c) == 0) q.offer(c);

        StringBuilder sb = new StringBuilder();
        while (!q.isEmpty()) {
            char c = q.poll(); sb.append(c);
            for (char nei : graph.get(c))
                if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
        }
        return sb.length() == inDeg.size() ? sb.toString() : "";
    }

    public static void main(String[] args) {
        Problem25_AlienDictionaryWithInvalidCases solver = new Problem25_AlienDictionaryWithInvalidCases();
        System.out.println(solver.alienOrder(new String[]{"abc","ab"})); // "" (invalid)
        System.out.println(solver.alienOrder(new String[]{"z","x","z"})); // "" (cycle)
    }
}
