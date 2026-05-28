import java.util.*;

/**
 * Problem 31: Alien Dictionary
 * Given a sorted list of words in an alien language, derive the character order.
 *
 * Approach: Build a directed graph from adjacent word comparisons, then topological sort (BFS/Kahn's).
 * HashMap stores adjacency list and in-degree.
 *
 * Time Complexity: O(C) where C = total characters in all words
 * Space Complexity: O(1) - at most 26 chars
 *
 * Production Analogy: Like dependency resolution in package managers (npm, maven).
 * Determine installation order from pairwise dependency constraints.
 */
public class Problem31_AlienDictionary {
    public String alienOrder(String[] words) {
        Map<Character, Set<Character>> graph = new HashMap<>();
        Map<Character, Integer> inDegree = new HashMap<>();
        // Initialize all characters
        for (String w : words) for (char c : w.toCharArray()) {
            graph.putIfAbsent(c, new HashSet<>());
            inDegree.putIfAbsent(c, 0);
        }
        // Build graph from adjacent words
        for (int i = 0; i < words.length - 1; i++) {
            String w1 = words[i], w2 = words[i+1];
            if (w1.length() > w2.length() && w1.startsWith(w2)) return ""; // invalid
            for (int j = 0; j < Math.min(w1.length(), w2.length()); j++) {
                if (w1.charAt(j) != w2.charAt(j)) {
                    if (graph.get(w1.charAt(j)).add(w2.charAt(j))) {
                        inDegree.merge(w2.charAt(j), 1, Integer::sum);
                    }
                    break;
                }
            }
        }
        // BFS topological sort
        Queue<Character> queue = new LinkedList<>();
        for (var e : inDegree.entrySet()) if (e.getValue() == 0) queue.add(e.getKey());
        StringBuilder sb = new StringBuilder();
        while (!queue.isEmpty()) {
            char c = queue.poll();
            sb.append(c);
            for (char next : graph.get(c)) {
                inDegree.merge(next, -1, Integer::sum);
                if (inDegree.get(next) == 0) queue.add(next);
            }
        }
        return sb.length() == inDegree.size() ? sb.toString() : "";
    }

    public static void main(String[] args) {
        Problem31_AlienDictionary sol = new Problem31_AlienDictionary();
        System.out.println(sol.alienOrder(new String[]{"wrt","wrf","er","ett","rftt"})); // "wertf"
        System.out.println(sol.alienOrder(new String[]{"z","x"})); // "zx"
        System.out.println(sol.alienOrder(new String[]{"z","x","z"})); // "" (cycle)
        System.out.println(sol.alienOrder(new String[]{"abc","ab"})); // "" (invalid prefix)
    }
}
