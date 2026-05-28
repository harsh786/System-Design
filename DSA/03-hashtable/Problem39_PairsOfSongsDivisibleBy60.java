import java.util.*;

/**
 * Problem 39: Pairs of Songs With Total Durations Divisible by 60
 * Count pairs where (time[i] + time[j]) % 60 == 0.
 *
 * Approach: Like Two Sum but with modular arithmetic. Store count of remainders.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(1) - array of 60
 *
 * Production Analogy: Like pairing tasks in a scheduler where combined execution
 * time must fit exactly into fixed time slots.
 */
public class Problem39_PairsOfSongsDivisibleBy60 {
    public int numPairsDivisibleBy60(int[] time) {
        int[] remainders = new int[60];
        int count = 0;
        for (int t : time) {
            int r = t % 60;
            int complement = (60 - r) % 60;
            count += remainders[complement];
            remainders[r]++;
        }
        return count;
    }

    public static void main(String[] args) {
        Problem39_PairsOfSongsDivisibleBy60 sol = new Problem39_PairsOfSongsDivisibleBy60();
        System.out.println(sol.numPairsDivisibleBy60(new int[]{30,20,150,100,40})); // 3
        System.out.println(sol.numPairsDivisibleBy60(new int[]{60,60,60})); // 3
    }
}
