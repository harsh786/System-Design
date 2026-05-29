/**
 * Problem: Prison Cells After N Days (LeetCode 957)
 * Approach: Cycle detection - states repeat with period ≤ 14
 * Complexity: O(1) time (bounded states), O(1) space
 * Production Analogy: Detecting periodic patterns in system state for optimization
 */
import java.util.*;
public class Problem13_PrisonCellsAfterNDays {
    public int[] prisonAfterNDays(int[] cells, int n) {
        Map<String, Integer> seen = new HashMap<>();
        while (n > 0) {
            String key = Arrays.toString(cells);
            if (seen.containsKey(key)) { n %= seen.get(key) - n; }
            if (n <= 0) break;
            seen.put(key, n);
            int[] next = new int[8];
            for (int i = 1; i < 7; i++) next[i] = cells[i-1]==cells[i+1] ? 1 : 0;
            cells = next;
            n--;
        }
        return cells;
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem13_PrisonCellsAfterNDays()
            .prisonAfterNDays(new int[]{0,1,0,1,1,0,0,1}, 7)));
    }
}
