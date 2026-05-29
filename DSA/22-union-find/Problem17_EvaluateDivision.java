import java.util.*;

/**
 * Problem 17: Evaluate Division (LeetCode 399) - Union-Find with weights
 * 
 * Given equations a/b = k, answer queries a/b = ?
 * 
 * Weighted Union-Find: parent[x] stores the ratio x/parent[x].
 * Path compression updates weights along the path.
 * find(x) returns root and updates weight[x] = x/root.
 * 
 * Time: O((E+Q) * α(V)), Space: O(V)
 * 
 * Production Analogy: Currency exchange rate graph - given some exchange rates,
 * derive any pair's exchange rate through transitive relationships.
 */
public class Problem17_EvaluateDivision {
    
    Map<String, String> parent = new HashMap<>();
    Map<String, Double> weight = new HashMap<>(); // weight[x] = x / parent[x]
    
    public double[] calcEquation(List<List<String>> equations, double[] values, List<List<String>> queries) {
        for (int i = 0; i < equations.size(); i++) {
            String a = equations.get(i).get(0), b = equations.get(i).get(1);
            if (!parent.containsKey(a)) { parent.put(a, a); weight.put(a, 1.0); }
            if (!parent.containsKey(b)) { parent.put(b, b); weight.put(b, 1.0); }
            union(a, b, values[i]);
        }
        
        double[] result = new double[queries.size()];
        for (int i = 0; i < queries.size(); i++) {
            String a = queries.get(i).get(0), b = queries.get(i).get(1);
            if (!parent.containsKey(a) || !parent.containsKey(b)) { result[i] = -1.0; continue; }
            String ra = find(a), rb = find(b);
            if (!ra.equals(rb)) { result[i] = -1.0; continue; }
            result[i] = weight.get(a) / weight.get(b); // (a/root) / (b/root) = a/b
        }
        return result;
    }
    
    private String find(String x) {
        if (!parent.get(x).equals(x)) {
            String root = find(parent.get(x));
            weight.put(x, weight.get(x) * weight.get(parent.get(x)));
            parent.put(x, root);
        }
        return parent.get(x);
    }
    
    private void union(String a, String b, double val) {
        String ra = find(a), rb = find(b);
        if (ra.equals(rb)) return;
        parent.put(ra, rb);
        // ra -> rb weight: a/ra's weight * val / (b/rb's weight) ... 
        // weight[ra] = ra/parent[ra] = ra/rb
        // a = weight[a] * ra, b = weight[b] * rb, a/b = val
        // weight[a]*ra / (weight[b]*rb) = val => ra/rb = val*weight[b]/weight[a]
        weight.put(ra, val * weight.get(b) / weight.get(a));
    }
    
    public static void main(String[] args) {
        Problem17_EvaluateDivision sol = new Problem17_EvaluateDivision();
        List<List<String>> eq = Arrays.asList(Arrays.asList("a","b"), Arrays.asList("b","c"));
        double[] vals = {2.0, 3.0};
        List<List<String>> q = Arrays.asList(
            Arrays.asList("a","c"), Arrays.asList("b","a"),
            Arrays.asList("a","e"), Arrays.asList("a","a"), Arrays.asList("x","x"));
        System.out.println(Arrays.toString(sol.calcEquation(eq, vals, q)));
        // [6.0, 0.5, -1.0, 1.0, -1.0]
    }
}
