/**
 * Problem: Conway's Game of Life on Infinite Grid
 * Approach: HashSet of live cells, count neighbors, apply rules
 * Complexity: O(live cells) per generation
 * Production Analogy: Sparse state representation for large-scale distributed simulations
 */
import java.util.*;
public class Problem48_ConwayGameOfLifeInfinite {
    public Set<long[]> nextGeneration(Set<String> liveCells) {
        Map<String, Integer> neighborCount = new HashMap<>();
        for (String cell : liveCells) {
            String[] parts = cell.split(",");
            int r = Integer.parseInt(parts[0]), c = Integer.parseInt(parts[1]);
            for (int dr = -1; dr <= 1; dr++)
                for (int dc = -1; dc <= 1; dc++)
                    if (dr != 0 || dc != 0)
                        neighborCount.merge((r+dr)+","+(c+dc), 1, Integer::sum);
        }
        Set<long[]> next = new HashSet<>();
        Set<String> nextSet = new HashSet<>();
        for (Map.Entry<String, Integer> e : neighborCount.entrySet()) {
            int cnt = e.getValue();
            if (cnt == 3 || (cnt == 2 && liveCells.contains(e.getKey())))
                nextSet.add(e.getKey());
        }
        System.out.println("Next gen live cells: " + nextSet.size());
        return next;
    }

    public static void main(String[] args) {
        Set<String> live = new HashSet<>(Arrays.asList("0,1", "1,2", "2,0", "2,1", "2,2")); // glider
        Problem48_ConwayGameOfLifeInfinite sol = new Problem48_ConwayGameOfLifeInfinite();
        sol.nextGeneration(live);
    }
}
