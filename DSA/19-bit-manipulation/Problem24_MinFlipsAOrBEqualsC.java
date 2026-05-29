/**
 * Problem 24: Minimum Flips to Make a OR b Equal to c
 * 
 * Approach: For each bit position, check what flips are needed.
 * If c_bit=1: need at least one of a_bit,b_bit to be 1 (flip cost 1 if both 0).
 * If c_bit=0: both a_bit and b_bit must be 0 (flip each 1).
 * Time: O(32), Space: O(1)
 * 
 * Production Analogy: Minimum config changes to achieve desired combined feature state.
 */
public class Problem24_MinFlipsAOrBEqualsC {
    public static int minFlips(int a, int b, int c) {
        int flips = 0;
        for (int i = 0; i < 32; i++) {
            int ai = (a >> i) & 1, bi = (b >> i) & 1, ci = (c >> i) & 1;
            if (ci == 1) {
                if (ai == 0 && bi == 0) flips++;
            } else {
                flips += ai + bi;
            }
        }
        return flips;
    }

    public static void main(String[] args) {
        System.out.println(minFlips(2, 6, 5)); // 3
        System.out.println(minFlips(4, 2, 7)); // 1
        System.out.println(minFlips(1, 2, 3)); // 0
    }
}
