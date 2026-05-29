import java.util.*;

/**
 * Problem 9: 2-SAT Problem using SCC
 * 
 * 2-SAT: Given a Boolean formula in CNF with exactly 2 literals per clause,
 * determine if it's satisfiable and find an assignment.
 * 
 * Key reduction to graph/SCC:
 * - For each variable x, create nodes x and ¬x
 * - Clause (a ∨ b) becomes implications: ¬a → b AND ¬b → a
 * - Formula is satisfiable iff no variable x is in same SCC as ¬x
 * - Assignment: In topological order of SCCs, assign TRUE to variables
 *   whose positive literal appears in a later SCC than their negation.
 * 
 * Time: O(V + E) = O(n + m) where n=variables, m=clauses
 */
public class Problem09_TwoSAT {

    private int n; // number of variables
    private List<List<Integer>> graph;
    
    // Variable x: node 2*x (positive), node 2*x+1 (negative)
    private int pos(int x) { return 2 * x; }
    private int neg(int x) { return 2 * x + 1; }
    private int negate(int lit) { return lit ^ 1; }

    public Problem09_TwoSAT(int numVars) {
        this.n = numVars;
        graph = new ArrayList<>();
        for (int i = 0; i < 2 * n; i++) graph.add(new ArrayList<>());
    }

    // Add clause (a OR b) where a,b are literals (use pos(x) or neg(x))
    public void addClause(int a, int b) {
        // ¬a → b
        graph.get(negate(a)).add(b);
        // ¬b → a
        graph.get(negate(b)).add(a);
    }

    public boolean[] solve() {
        int totalNodes = 2 * n;
        // Find SCCs using Kosaraju's
        boolean[] visited = new boolean[totalNodes];
        Deque<Integer> order = new ArrayDeque<>();
        for (int i = 0; i < totalNodes; i++)
            if (!visited[i]) dfs1(i, visited, order);
        
        // Build transpose
        List<List<Integer>> trans = new ArrayList<>();
        for (int i = 0; i < totalNodes; i++) trans.add(new ArrayList<>());
        for (int u = 0; u < totalNodes; u++)
            for (int v : graph.get(u)) trans.get(v).add(u);
        
        // Second DFS
        int[] comp = new int[totalNodes];
        Arrays.fill(comp, -1);
        int numComp = 0;
        while (!order.isEmpty()) {
            int v = order.pop();
            if (comp[v] == -1) {
                dfs2(v, trans, comp, numComp++);
            }
        }
        
        // Check satisfiability and build assignment
        boolean[] assignment = new boolean[n];
        for (int i = 0; i < n; i++) {
            if (comp[pos(i)] == comp[neg(i)]) return null; // Unsatisfiable
            // Variable is TRUE if neg appears in earlier SCC (processed later in Kosaraju)
            assignment[i] = comp[pos(i)] > comp[neg(i)];
        }
        return assignment;
    }

    private void dfs1(int u, boolean[] visited, Deque<Integer> order) {
        visited[u] = true;
        for (int v : graph.get(u)) if (!visited[v]) dfs1(v, visited, order);
        order.push(u);
    }

    private void dfs2(int u, List<List<Integer>> graph, int[] comp, int id) {
        comp[u] = id;
        for (int v : graph.get(u)) if (comp[v] == -1) dfs2(v, graph, comp, id);
    }

    public static void main(String[] args) {
        // Example: (x0 ∨ x1) ∧ (¬x0 ∨ x2) ∧ (¬x1 ∨ ¬x2)
        Problem09_TwoSAT sat = new Problem09_TwoSAT(3);
        sat.addClause(sat.pos(0), sat.pos(1));   // x0 ∨ x1
        sat.addClause(sat.neg(0), sat.pos(2));   // ¬x0 ∨ x2
        sat.addClause(sat.neg(1), sat.neg(2));   // ¬x1 ∨ ¬x2
        
        boolean[] result = sat.solve();
        System.out.println("2-SAT Problem");
        System.out.println("Formula: (x0 ∨ x1) ∧ (¬x0 ∨ x2) ∧ (¬x1 ∨ ¬x2)");
        if (result != null) {
            System.out.print("Satisfiable! Assignment: ");
            for (int i = 0; i < result.length; i++) System.out.print("x" + i + "=" + result[i] + " ");
            System.out.println();
        } else {
            System.out.println("Unsatisfiable");
        }

        // Unsatisfiable example: (x0) ∧ (¬x0)
        Problem09_TwoSAT sat2 = new Problem09_TwoSAT(1);
        sat2.addClause(sat2.pos(0), sat2.pos(0));  // x0
        sat2.addClause(sat2.neg(0), sat2.neg(0));  // ¬x0
        boolean[] result2 = sat2.solve();
        System.out.println("\nFormula: (x0) ∧ (¬x0)");
        System.out.println(result2 != null ? "Satisfiable" : "Unsatisfiable");
    }
}
