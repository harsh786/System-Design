/**
 * Problem: Pairs of Songs With Total Durations Divisible by 60 (LeetCode 1010)
 * Approach: Count remainders mod 60, pair complements
 * Complexity: O(n) time, O(1) space (60 buckets)
 * Production Analogy: Modular pairing in scheduling aligned time slots
 */
public class Problem40_PairsOfSongsDivisibleBy60 {
    public int numPairsDivisibleBy60(int[] time) {
        int[] count = new int[60];
        int pairs = 0;
        for (int t : time) {
            int rem = t % 60;
            pairs += count[(60 - rem) % 60];
            count[rem]++;
        }
        return pairs;
    }
    public static void main(String[] args) {
        System.out.println(new Problem40_PairsOfSongsDivisibleBy60()
            .numPairsDivisibleBy60(new int[]{30,20,150,100,40})); // 3
    }
}
