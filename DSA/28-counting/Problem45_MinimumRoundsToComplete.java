/**
 * Problem: Minimum Rounds to Complete All Tasks (LeetCode 2244)
 * Approach: Count frequencies; for each, ceil(freq/3) rounds needed (impossible if freq==1)
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Batch processing optimization with minimum batch sizes
 */
import java.util.*;
public class Problem45_MinimumRoundsToComplete {
    public int minimumRounds(int[] tasks) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int t : tasks) freq.merge(t, 1, Integer::sum);
        int rounds = 0;
        for (int count : freq.values()) {
            if (count == 1) return -1;
            rounds += (count + 2) / 3; // ceil(count/3)
        }
        return rounds;
    }
    public static void main(String[] args) {
        System.out.println(new Problem45_MinimumRoundsToComplete()
            .minimumRounds(new int[]{2,2,3,3,2,4,4,4,4,4})); // 4
    }
}
