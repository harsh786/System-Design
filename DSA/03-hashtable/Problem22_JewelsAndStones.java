import java.util.*;

/**
 * Problem 22: Jewels and Stones
 * Count how many stones are jewels.
 *
 * Time Complexity: O(j + s)
 * Space Complexity: O(j)
 *
 * Production Analogy: Like filtering events by a whitelist/allowlist in a security system.
 */
public class Problem22_JewelsAndStones {
    public int numJewelsInStones(String jewels, String stones) {
        Set<Character> set = new HashSet<>();
        for (char c : jewels.toCharArray()) set.add(c);
        int count = 0;
        for (char c : stones.toCharArray()) if (set.contains(c)) count++;
        return count;
    }

    public static void main(String[] args) {
        Problem22_JewelsAndStones sol = new Problem22_JewelsAndStones();
        System.out.println(sol.numJewelsInStones("aA", "aAAbbbb")); // 3
        System.out.println(sol.numJewelsInStones("z", "ZZ")); // 0
    }
}
