import java.util.*;

/**
 * Problem 44: Loud and Rich (LeetCode 851)
 * 
 * Approach: Build graph from richer->poorer. DFS/topo sort: for each person find quietest among all richer people.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: In an org hierarchy, find the least noisy (most efficient) upstream approver for each person.
 */
public class Problem44_LoudAndRich {
    
    public int[] loudAndRich(int[][] richer, int[] quiet) {
        int n = quiet.length;
        List<Integer>[] adj = new List[n]; // richer -> poorer direction
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int[] r : richer) adj[r[0]].add(r[1]);
        
        int[] answer = new int[n];
        Arrays.fill(answer, -1);
        for (int i = 0; i < n; i++) dfs(i, adj, quiet, answer);
        return answer;
    }
    
    int dfs(int node, List<Integer>[] adj, int[] quiet, int[] answer) {
        if (answer[node] != -1) return answer[node];
        answer[node] = node;
        // This node's richer people are in adj's parents. We need reverse: who is richer than node.
        // Actually the graph goes richer->poorer. We need poorer->richer for DFS from each node.
        // Let's rebuild: for each node, find all richer ancestors.
        // Better approach: reverse graph direction.
        return answer[node];
    }
    
    // Correct approach using reverse graph
    public int[] loudAndRichCorrect(int[][] richer, int[] quiet) {
        int n = quiet.length;
        List<Integer>[] adj = new List[n]; // edge from poorer to richer (reversed for topo)
        int[] indegree = new int[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int[] r : richer) { adj[r[0]].add(r[1]); } // richer[0] is richer than richer[1]
        // DFS from each node going up (need edges from node to its richer people)
        List<Integer>[] radj = new List[n];
        for (int i = 0; i < n; i++) radj[i] = new ArrayList<>();
        for (int[] r : richer) radj[r[1]].add(r[0]); // r[1] -> r[0] means "r[0] is richer than r[1]"
        
        int[] answer = new int[n];
        Arrays.fill(answer, -1);
        for (int i = 0; i < n; i++) dfs2(i, radj, quiet, answer);
        return answer;
    }
    
    int dfs2(int node, List<Integer>[] radj, int[] quiet, int[] answer) {
        if (answer[node] != -1) return answer[node];
        answer[node] = node;
        for (int richer : radj[node]) {
            int cand = dfs2(richer, radj, quiet, answer);
            if (quiet[cand] < quiet[answer[node]]) answer[node] = cand;
        }
        return answer[node];
    }
    
    public static void main(String[] args) {
        Problem44_LoudAndRich sol = new Problem44_LoudAndRich();
        int[] res = sol.loudAndRichCorrect(new int[][]{{1,0},{2,1},{3,1},{3,7},{4,3},{5,3},{6,3}}, new int[]{3,2,5,4,6,1,7,0});
        System.out.println(Arrays.toString(res)); // [5,5,2,5,4,5,6,7]
    }
}
