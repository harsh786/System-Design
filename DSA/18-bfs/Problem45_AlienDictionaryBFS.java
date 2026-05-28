import java.util.*;

/**
 * Problem: Alien Dictionary BFS (LeetCode 269)
 * Approach: Kahn's topological sort - build char graph, BFS from 0-indegree chars
 * Time: O(C) total characters, Space: O(U) unique chars
 * Production Analogy: Inferring deployment ordering from observed event sequences using BFS
 */
public class Problem45_AlienDictionaryBFS {
    public String alienOrder(String[] words) {
        Map<Character, Set<Character>> graph = new HashMap<>();
        Map<Character, Integer> indegree = new HashMap<>();
        for (String w : words) for (char c : w.toCharArray()) { graph.putIfAbsent(c, new HashSet<>()); indegree.putIfAbsent(c, 0); }
        for (int i = 0; i < words.length - 1; i++) {
            String w1 = words[i], w2 = words[i+1];
            if (w1.length() > w2.length() && w1.startsWith(w2)) return "";
            for (int j = 0; j < Math.min(w1.length(), w2.length()); j++) {
                if (w1.charAt(j) != w2.charAt(j)) {
                    if (graph.get(w1.charAt(j)).add(w2.charAt(j)))
                        indegree.merge(w2.charAt(j), 1, Integer::sum);
                    break;
                }
            }
        }
        Queue<Character> q = new LinkedList<>();
        for (char c : indegree.keySet()) if (indegree.get(c) == 0) q.offer(c);
        StringBuilder sb = new StringBuilder();
        while (!q.isEmpty()) {
            char c = q.poll(); sb.append(c);
            for (char next : graph.get(c))
                if (indegree.merge(next, -1, Integer::sum) == 0) q.offer(next);
        }
        return sb.length() == indegree.size() ? sb.toString() : "";
    }

    public static void main(String[] args) {
        System.out.println(new Problem45_AlienDictionaryBFS().alienOrder(new String[]{"wrt","wrf","er","ett","rftt"}));
    }
}
