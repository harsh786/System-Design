import java.util.*;

/**
 * Problem: Alien Dictionary
 * Given sorted words in alien language, derive character order.
 *
 * Approach: Build graph from adjacent word pairs, then topological sort
 *
 * Time Complexity: O(C) where C = total chars in all words
 * Space Complexity: O(1) - at most 26 nodes
 *
 * Production Analogy: Inferring priority rules from observed ordering patterns in logs.
 */
public class Problem03_AlienDictionary {

    public String alienOrder(String[] words) {
        Map<Character, Set<Character>> graph = new HashMap<>();
        Map<Character, Integer> inDegree = new HashMap<>();

        for (String w : words)
            for (char c : w.toCharArray()) {
                graph.putIfAbsent(c, new HashSet<>());
                inDegree.putIfAbsent(c, 0);
            }

        for (int i = 0; i < words.length - 1; i++) {
            String w1 = words[i], w2 = words[i + 1];
            if (w1.length() > w2.length() && w1.startsWith(w2)) return "";
            for (int j = 0; j < Math.min(w1.length(), w2.length()); j++) {
                char c1 = w1.charAt(j), c2 = w2.charAt(j);
                if (c1 != c2) {
                    if (!graph.get(c1).contains(c2)) {
                        graph.get(c1).add(c2);
                        inDegree.put(c2, inDegree.get(c2) + 1);
                    }
                    break;
                }
            }
        }

        Queue<Character> queue = new LinkedList<>();
        for (char c : inDegree.keySet())
            if (inDegree.get(c) == 0) queue.offer(c);

        StringBuilder sb = new StringBuilder();
        while (!queue.isEmpty()) {
            char c = queue.poll();
            sb.append(c);
            for (char nei : graph.get(c))
                if (inDegree.merge(nei, -1, Integer::sum) == 0) queue.offer(nei);
        }
        return sb.length() == inDegree.size() ? sb.toString() : "";
    }

    public static void main(String[] args) {
        Problem03_AlienDictionary solver = new Problem03_AlienDictionary();
        System.out.println(solver.alienOrder(new String[]{"wrt","wrf","er","ett","rftt"}));
    }
}
