/**
 * Problem: Circular Game Losers (LeetCode 2682)
 * Approach: Simulate passing with increasing steps until repeat
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Token ring protocol with failure detection
 */
import java.util.*;
public class Problem40_CircularGameLosers {
    public int[] circularGameLosers(int n, int k) {
        boolean[] received = new boolean[n];
        int cur = 0, turn = 1;
        while (!received[cur]) {
            received[cur] = true;
            cur = (cur + turn * k) % n;
            turn++;
        }
        List<Integer> losers = new ArrayList<>();
        for (int i = 0; i < n; i++) if (!received[i]) losers.add(i+1);
        return losers.stream().mapToInt(Integer::intValue).toArray();
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem40_CircularGameLosers().circularGameLosers(5, 2)));
    }
}
