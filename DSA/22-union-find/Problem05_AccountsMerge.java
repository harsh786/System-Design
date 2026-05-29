import java.util.*;

/**
 * Problem 5: Accounts Merge (LeetCode 721)
 * 
 * Given accounts where each account has a name and emails, merge accounts
 * that share at least one email. Return merged accounts with sorted emails.
 * 
 * Approach: Map each email to an ID. Union emails that belong to same account.
 * Group emails by their root parent, then build result.
 * 
 * Time: O(N * α(N) + N*logN) where N = total emails, Space: O(N)
 * 
 * Production Analogy: User identity resolution - when a user signs up with
 * different emails across services, we need to merge their profiles into one
 * unified identity (like Segment's identity graph).
 */
public class Problem05_AccountsMerge {
    
    int[] parent, rank;
    
    public List<List<String>> accountsMerge(List<List<String>> accounts) {
        Map<String, Integer> emailToId = new HashMap<>();
        Map<String, String> emailToName = new HashMap<>();
        int id = 0;
        
        // Assign IDs to each email
        for (List<String> acc : accounts) {
            String name = acc.get(0);
            for (int i = 1; i < acc.size(); i++) {
                if (!emailToId.containsKey(acc.get(i))) {
                    emailToId.put(acc.get(i), id++);
                }
                emailToName.put(acc.get(i), name);
            }
        }
        
        parent = new int[id]; rank = new int[id];
        for (int i = 0; i < id; i++) parent[i] = i;
        
        // Union emails in same account
        for (List<String> acc : accounts) {
            int firstId = emailToId.get(acc.get(1));
            for (int i = 2; i < acc.size(); i++) {
                union(firstId, emailToId.get(acc.get(i)));
            }
        }
        
        // Group emails by root
        Map<Integer, List<String>> groups = new HashMap<>();
        for (String email : emailToId.keySet()) {
            int root = find(emailToId.get(email));
            groups.computeIfAbsent(root, k -> new ArrayList<>()).add(email);
        }
        
        // Build result
        List<List<String>> result = new ArrayList<>();
        for (List<String> emails : groups.values()) {
            Collections.sort(emails);
            String name = emailToName.get(emails.get(0));
            List<String> merged = new ArrayList<>();
            merged.add(name);
            merged.addAll(emails);
            result.add(merged);
        }
        return result;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        if (rank[px] < rank[py]) parent[px] = py;
        else if (rank[px] > rank[py]) parent[py] = px;
        else { parent[py] = px; rank[px]++; }
    }
    
    public static void main(String[] args) {
        Problem05_AccountsMerge sol = new Problem05_AccountsMerge();
        
        List<List<String>> accounts = Arrays.asList(
            Arrays.asList("John","john00@mail.com","john_neo@mail.com","john_neo00@mail.com"),
            Arrays.asList("John","john01@mail.com"),
            Arrays.asList("John","john00@mail.com","john01@mail.com"),
            Arrays.asList("Mary","mary@mail.com")
        );
        
        List<List<String>> result = sol.accountsMerge(accounts);
        for (List<String> acc : result) System.out.println(acc);
        // John's first and third accounts merge (share john00@mail.com)
        // Then that merges with second (share john01@mail.com via third)
    }
}
