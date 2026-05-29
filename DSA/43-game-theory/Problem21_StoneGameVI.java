import java.util.*;

public class Problem21_StoneGameVI {
    // 1686. Stone Game VI: Two arrays of values. Each player picks a stone (both see different values).
    // Greedy: sort by sum of values.
    
    public int stoneGameVI(int[] aliceValues, int[] bobValues) {
        int n = aliceValues.length;
        Integer[] idx = new Integer[n];
        for (int i = 0; i < n; i++) idx[i] = i;
        Arrays.sort(idx, (a, b) -> (bobValues[b] + aliceValues[b]) - (bobValues[a] + aliceValues[a]));
        int alice = 0, bob = 0;
        for (int i = 0; i < n; i++) {
            if (i % 2 == 0) alice += aliceValues[idx[i]];
            else bob += bobValues[idx[i]];
        }
        return Integer.compare(alice, bob);
    }
    
    public static void main(String[] args) {
        Problem21_StoneGameVI sol = new Problem21_StoneGameVI();
        System.out.println(sol.stoneGameVI(new int[]{1,3}, new int[]{2,1})); // 1
        System.out.println(sol.stoneGameVI(new int[]{1,2}, new int[]{3,1})); // 0
    }
}
