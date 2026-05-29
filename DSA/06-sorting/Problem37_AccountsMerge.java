import java.util.*;

/**
 * Problem 37: Accounts Merge
 * 
 * Merge accounts belonging to the same person (share common email).
 * 
 * Approach: Union-Find. Each email gets a parent. Emails in same account are unioned.
 * Then group by root and sort emails.
 * Time Complexity: O(n * k * α(n)) for union-find + O(nk log(nk)) for sorting
 * Space Complexity: O(n * k)
 * 
 * Production Analogy: Identity resolution in customer data platforms - merging duplicate
 * user profiles that share common identifiers (email, phone, device ID).
 */
public class Problem37_AccountsMerge {
    
    private Map<String, String> parent = new HashMap<>();
    
    private String find(String x) {
        if (!parent.get(x).equals(x)) parent.put(x, find(parent.get(x)));
        return parent.get(x);
    }
    
    private void union(String x, String y) {
        parent.put(find(x), find(y));
    }
    
    public List<List<String>> accountsMerge(List<List<String>> accounts) {
        Map<String, String> emailToName = new HashMap<>();
        
        for (List<String> account : accounts) {
            String name = account.get(0);
            for (int i = 1; i < account.size(); i++) {
                parent.putIfAbsent(account.get(i), account.get(i));
                emailToName.put(account.get(i), name);
                if (i > 1) union(account.get(i), account.get(1));
            }
        }
        
        Map<String, TreeSet<String>> groups = new HashMap<>();
        for (String email : parent.keySet()) {
            String root = find(email);
            groups.computeIfAbsent(root, k -> new TreeSet<>()).add(email);
        }
        
        List<List<String>> result = new ArrayList<>();
        for (var entry : groups.entrySet()) {
            List<String> list = new ArrayList<>();
            list.add(emailToName.get(entry.getKey()));
            list.addAll(entry.getValue());
            result.add(list);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem37_AccountsMerge sol = new Problem37_AccountsMerge();
        
        List<List<String>> accounts = Arrays.asList(
            Arrays.asList("John","johnsmith@mail.com","john_newyork@mail.com"),
            Arrays.asList("John","johnsmith@mail.com","john00@mail.com"),
            Arrays.asList("Mary","mary@mail.com"),
            Arrays.asList("John","johnnybravo@mail.com")
        );
        
        List<List<String>> result = sol.accountsMerge(accounts);
        System.out.println("Test 1:");
        for (List<String> acc : result) System.out.println("  " + acc);
    }
}
