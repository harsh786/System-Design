import java.util.*;

/**
 * Problem 31: Satisfiability of Equality Equations (LeetCode 990)
 * 
 * Approach: Union-Find. First pass: union all '==' pairs. Second pass: check '!=' conflicts.
 * Time: O(N), Space: O(1) (26 chars)
 * 
 * Production Analogy: Validating config constraints - equality groups must not conflict with inequality rules.
 */
public class Problem31_SatisfiabilityOfEqualityEquations {
    
    int[] parent = new int[26];
    int find(int x) { return parent[x] == x ? x : (parent[x] = find(parent[x])); }
    
    public boolean equationsPossible(String[] equations) {
        for (int i = 0; i < 26; i++) parent[i] = i;
        for (String eq : equations)
            if (eq.charAt(1) == '=') parent[find(eq.charAt(0)-'a')] = find(eq.charAt(3)-'a');
        for (String eq : equations)
            if (eq.charAt(1) == '!' && find(eq.charAt(0)-'a') == find(eq.charAt(3)-'a')) return false;
        return true;
    }
    
    public static void main(String[] args) {
        Problem31_SatisfiabilityOfEqualityEquations sol = new Problem31_SatisfiabilityOfEqualityEquations();
        System.out.println(sol.equationsPossible(new String[]{"a==b","b!=a"})); // false
        sol = new Problem31_SatisfiabilityOfEqualityEquations(); sol.parent = new int[26]; for(int i=0;i<26;i++) sol.parent[i]=i;
        System.out.println(sol.equationsPossible(new String[]{"b==a","a==b"})); // true
        sol = new Problem31_SatisfiabilityOfEqualityEquations(); sol.parent = new int[26]; for(int i=0;i<26;i++) sol.parent[i]=i;
        System.out.println(sol.equationsPossible(new String[]{"a==b","b==c","a==c"})); // true
    }
}
