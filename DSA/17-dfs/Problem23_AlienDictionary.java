import java.util.*;

/**
 * Problem: Alien Dictionary (LeetCode 269)
 * Approach: Build graph from adjacent word comparisons, DFS topological sort
 * Time: O(C) total characters, Space: O(U+min(U^2, N)) U=unique chars
 * Production Analogy: Inferring ordering constraints from observed sequences in event sourcing
 */
public class Problem23_AlienDictionary {
    public String alienOrder(String[] words) {
        Map<Character, Set<Character>> graph = new HashMap<>();
        for (String w : words) for (char c : w.toCharArray()) graph.putIfAbsent(c, new HashSet<>());
        for (int i = 0; i < words.length - 1; i++) {
            String w1 = words[i], w2 = words[i+1];
            if (w1.length() > w2.length() && w1.startsWith(w2)) return "";
            for (int j = 0; j < Math.min(w1.length(), w2.length()); j++) {
                if (w1.charAt(j) != w2.charAt(j)) {
                    graph.get(w1.charAt(j)).add(w2.charAt(j));
                    break;
                }
            }
        }
        // DFS topo sort
        Map<Character, Integer> color = new HashMap<>();
        StringBuilder sb = new StringBuilder();
        for (char c : graph.keySet()) color.put(c, 0);
        for (char c : graph.keySet())
            if (color.get(c) == 0 && !dfs(graph, c, color, sb)) return "";
        return sb.reverse().toString();
    }

    private boolean dfs(Map<Character, Set<Character>> graph, char c, Map<Character, Integer> color, StringBuilder sb) {
        color.put(c, 1);
        for (char next : graph.get(c)) {
            if (color.get(next) == 1) return false;
            if (color.get(next) == 0 && !dfs(graph, next, color, sb)) return false;
        }
        color.put(c, 2);
        sb.append(c);
        return true;
    }

    public static void main(String[] args) {
        System.out.println(new Problem23_AlienDictionary().alienOrder(new String[]{"wrt","wrf","er","ett","rftt"}));
    }
}
