import java.util.*;

/**
 * Problem 10: Accounts Merge (LeetCode 721)
 * 
 * Approach: Union-Find on email indices. Group emails by connected components.
 * Time: O(N*K * α(N*K)), Space: O(N*K) where K = avg emails per account
 * 
 * Production Analogy: Merging duplicate user accounts in an identity service based on shared emails.
 */
public class Problem10_AccountsMerge {
    
    int[] parent, rank;
    int find(int x) { return parent[x] == x ? x : (parent[x] = find(parent[x])); }
    void union(int a, int b) { int pa=find(a),pb=find(b); if(pa!=pb){if(rank[pa]<rank[pb])parent[pa]=pb;else if(rank[pa]>rank[pb])parent[pb]=pa;else{parent[pb]=pa;rank[pa]++;}}}
    
    public List<List<String>> accountsMerge(List<List<String>> accounts) {
        Map<String, Integer> emailToId = new HashMap<>();
        Map<String, String> emailToName = new HashMap<>();
        int id = 0;
        for (List<String> acc : accounts) {
            String name = acc.get(0);
            for (int i = 1; i < acc.size(); i++) {
                if (!emailToId.containsKey(acc.get(i))) emailToId.put(acc.get(i), id++);
                emailToName.put(acc.get(i), name);
            }
        }
        parent = new int[id]; rank = new int[id];
        for (int i = 0; i < id; i++) parent[i] = i;
        for (List<String> acc : accounts)
            for (int i = 2; i < acc.size(); i++)
                union(emailToId.get(acc.get(1)), emailToId.get(acc.get(i)));
        
        Map<Integer, TreeSet<String>> groups = new HashMap<>();
        for (String email : emailToId.keySet()) {
            int root = find(emailToId.get(email));
            groups.computeIfAbsent(root, k -> new TreeSet<>()).add(email);
        }
        List<List<String>> result = new ArrayList<>();
        for (var entry : groups.entrySet()) {
            List<String> list = new ArrayList<>();
            String first = entry.getValue().first();
            list.add(emailToName.get(first));
            list.addAll(entry.getValue());
            result.add(list);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem10_AccountsMerge sol = new Problem10_AccountsMerge();
        List<List<String>> accounts = Arrays.asList(
            Arrays.asList("John","john@mail.com","john_neo@mail.com"),
            Arrays.asList("John","john@mail.com","john00@mail.com"),
            Arrays.asList("Mary","mary@mail.com"),
            Arrays.asList("John","johnnybravo@mail.com")
        );
        System.out.println(sol.accountsMerge(accounts));
    }
}
