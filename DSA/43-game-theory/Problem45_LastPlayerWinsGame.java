import java.util.*;

public class Problem45_LastPlayerWinsGame {
    // Last Player Wins: Generic combinatorial game. Given states and transitions,
    // determine if first player has a winning strategy.
    
    // BFS backward induction approach
    public boolean[] computeWinning(int n, List<List<Integer>> moves) {
        // moves.get(i) = list of states reachable from state i
        boolean[] winning = new boolean[n];
        int[] outDegree = new int[n];
        for (int i = 0; i < n; i++) outDegree[i] = moves.get(i).size();
        
        // Terminal states (no moves) are losing
        Queue<Integer> queue = new LinkedList<>();
        boolean[] determined = new boolean[n];
        
        // Build reverse graph
        List<List<Integer>> rev = new ArrayList<>();
        for (int i = 0; i < n; i++) rev.add(new ArrayList<>());
        for (int i = 0; i < n; i++)
            for (int j : moves.get(i)) rev.get(j).add(i);
        
        for (int i = 0; i < n; i++) {
            if (outDegree[i] == 0) { determined[i] = true; winning[i] = false; queue.add(i); }
        }
        
        while (!queue.isEmpty()) {
            int u = queue.poll();
            for (int v : rev.get(u)) {
                if (determined[v]) continue;
                if (!winning[u]) { // u is losing, so v is winning (can move to u)
                    winning[v] = true; determined[v] = true; queue.add(v);
                } else { // u is winning, decrement v's options
                    outDegree[v]--;
                    if (outDegree[v] == 0) { winning[v] = false; determined[v] = true; queue.add(v); }
                }
            }
        }
        return winning;
    }
    
    public static void main(String[] args) {
        Problem45_LastPlayerWinsGame sol = new Problem45_LastPlayerWinsGame();
        List<List<Integer>> moves = new ArrayList<>();
        moves.add(Arrays.asList(1, 2)); // 0 -> 1, 2
        moves.add(Arrays.asList(3));    // 1 -> 3
        moves.add(Arrays.asList(3));    // 2 -> 3
        moves.add(new ArrayList<>());   // 3 terminal (losing)
        boolean[] result = sol.computeWinning(4, moves);
        System.out.println(Arrays.toString(result)); // [true, true, true, false]
    }
}
