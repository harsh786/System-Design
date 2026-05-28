import java.util.*;

/**
 * Problem 6: Alien Dictionary (LeetCode 269)
 * 
 * Approach: Build directed graph from adjacent word comparisons, then topological sort.
 * Time: O(C) where C = total chars, Space: O(1) since alphabet is bounded
 * 
 * Production Analogy: Inferring priority ordering from partial observations in an event-driven system.
 */
public class Problem06_AlienDictionary {
    
    public String alienOrder(String[] words) {
        Map<Character, Set<Character>> adj = new HashMap<>();
        Map<Character, Integer> indegree = new HashMap<>();
        for (String w : words) for (char c : w.toCharArray()) { adj.putIfAbsent(c, new HashSet<>()); indegree.putIfAbsent(c, 0); }
        
        for (int i = 0; i < words.length - 1; i++) {
            String w1 = words[i], w2 = words[i+1];
            if (w1.length() > w2.length() && w1.startsWith(w2)) return ""; // invalid
            for (int j = 0; j < Math.min(w1.length(), w2.length()); j++) {
                if (w1.charAt(j) != w2.charAt(j)) {
                    if (adj.get(w1.charAt(j)).add(w2.charAt(j)))
                        indegree.merge(w2.charAt(j), 1, Integer::sum);
                    break;
                }
            }
        }
        
        Queue<Character> q = new LinkedList<>();
        for (var e : indegree.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());
        StringBuilder sb = new StringBuilder();
        while (!q.isEmpty()) {
            char c = q.poll();
            sb.append(c);
            for (char next : adj.get(c))
                if (indegree.merge(next, -1, Integer::sum) == 0) q.offer(next);
        }
        return sb.length() == indegree.size() ? sb.toString() : "";
    }
    
    public static void main(String[] args) {
        Problem06_AlienDictionary sol = new Problem06_AlienDictionary();
        System.out.println(sol.alienOrder(new String[]{"wrt","wrf","er","ett","rftt"})); // "wertf"
        System.out.println(sol.alienOrder(new String[]{"z","x"})); // "zx"
        System.out.println(sol.alienOrder(new String[]{"z","x","z"})); // "" (cycle)
        System.out.println(sol.alienOrder(new String[]{"abc","ab"})); // "" (invalid prefix)
    }
}
