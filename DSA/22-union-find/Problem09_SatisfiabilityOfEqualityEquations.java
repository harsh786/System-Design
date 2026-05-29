import java.util.*;

/**
 * Problem 9: Satisfiability of Equality Equations (LeetCode 990)
 * 
 * Given equations like "a==b", "b!=c", determine if all can be satisfied simultaneously.
 * 
 * Approach: First pass - union all variables connected by '=='.
 * Second pass - check all '!=' constraints; if two vars in same component, contradiction.
 * 
 * Time: O(n * α(26)) = O(n), Space: O(1) (26 letters)
 * 
 * Production Analogy: Configuration validation - ensuring that equality constraints
 * (same region, same tier) don't conflict with inequality constraints (different AZ).
 */
public class Problem09_SatisfiabilityOfEqualityEquations {
    
    int[] parent = new int[26];
    
    public boolean equationsPossible(String[] equations) {
        for (int i = 0; i < 26; i++) parent[i] = i;
        
        // First pass: process equalities
        for (String eq : equations) {
            if (eq.charAt(1) == '=') {
                union(eq.charAt(0) - 'a', eq.charAt(3) - 'a');
            }
        }
        
        // Second pass: check inequalities
        for (String eq : equations) {
            if (eq.charAt(1) == '!') {
                if (find(eq.charAt(0) - 'a') == find(eq.charAt(3) - 'a')) return false;
            }
        }
        return true;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        parent[find(x)] = find(y);
    }
    
    public static void main(String[] args) {
        Problem09_SatisfiabilityOfEqualityEquations sol;
        
        sol = new Problem09_SatisfiabilityOfEqualityEquations();
        System.out.println(sol.equationsPossible(new String[]{"a==b","b!=a"})); // false
        
        sol = new Problem09_SatisfiabilityOfEqualityEquations();
        System.out.println(sol.equationsPossible(new String[]{"b==a","a==b"})); // true
        
        sol = new Problem09_SatisfiabilityOfEqualityEquations();
        System.out.println(sol.equationsPossible(new String[]{"a==b","b==c","a==c"})); // true
        
        sol = new Problem09_SatisfiabilityOfEqualityEquations();
        System.out.println(sol.equationsPossible(new String[]{"a==b","b!=c","c==a"})); // false
    }
}
