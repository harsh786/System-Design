import java.util.*;

/**
 * Problem: Accounts Merge (LeetCode 721)
 * Approach: Build graph of emails, DFS to find connected components
 * Time: O(N*K*logNK) where N=accounts, K=max emails, Space: O(NK)
 * Production Analogy: Deduplicating user identities across multiple authentication providers
 */
public class Problem19_AccountsMerge {
    public List<List<String>> accountsMerge(List<List<String>> accounts) {
        Map<String, Set<String>> graph = new HashMap<>();
        Map<String, String> emailToName = new HashMap<>();
        for (List<String> acc : accounts) {
            String name = acc.get(0);
            for (int i = 1; i < acc.size(); i++) {
                emailToName.put(acc.get(i), name);
                graph.computeIfAbsent(acc.get(i), k -> new HashSet<>());
                if (i > 1) {
                    graph.get(acc.get(1)).add(acc.get(i));
                    graph.get(acc.get(i)).add(acc.get(1));
                }
            }
        }
        Set<String> visited = new HashSet<>();
        List<List<String>> res = new ArrayList<>();
        for (String email : graph.keySet()) {
            if (visited.contains(email)) continue;
            List<String> component = new ArrayList<>();
            dfs(graph, email, visited, component);
            Collections.sort(component);
            component.add(0, emailToName.get(email));
            res.add(component);
        }
        return res;
    }

    private void dfs(Map<String, Set<String>> graph, String email, Set<String> visited, List<String> component) {
        visited.add(email);
        component.add(email);
        for (String next : graph.get(email))
            if (!visited.contains(next)) dfs(graph, next, visited, component);
    }

    public static void main(String[] args) {
        List<List<String>> accounts = Arrays.asList(
            Arrays.asList("John","john@mail.com","john_newyork@mail.com"),
            Arrays.asList("John","john@mail.com","john00@mail.com"),
            Arrays.asList("Mary","mary@mail.com"),
            Arrays.asList("John","johnnybravo@mail.com"));
        System.out.println(new Problem19_AccountsMerge().accountsMerge(accounts));
    }
}
