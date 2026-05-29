import java.util.*;

/**
 * Problem: Loud and Rich
 * For each person, find quietest person who is at least as rich.
 *
 * Approach: Topological sort from richest to poorest, propagating quietest answer
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Propagating optimal configurations down a hierarchy.
 */
public class Problem11_LoudAndRich {

    public int[] loudAndRich(int[][] richer, int[] quiet) {
        int n = quiet.length;
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] r : richer) { graph.get(r[0]).add(r[1]); inDeg[r[1]]++; }

        int[] answer = new int[n];
        for (int i = 0; i < n; i++) answer[i] = i;

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);

        while (!q.isEmpty()) {
            int node = q.poll();
            for (int nei : graph.get(node)) {
                if (quiet[answer[node]] < quiet[answer[nei]])
                    answer[nei] = answer[node];
                if (--inDeg[nei] == 0) q.offer(nei);
            }
        }
        return answer;
    }

    public static void main(String[] args) {
        Problem11_LoudAndRich solver = new Problem11_LoudAndRich();
        int[][] richer = {{1,0},{2,1},{3,1},{3,7},{4,3},{5,3},{6,3}};
        int[] quiet = {3,2,5,4,6,1,7,0};
        System.out.println(Arrays.toString(solver.loudAndRich(richer, quiet)));
    }
}
