/**
 * Problem: Jewels and Stones (LeetCode 771)
 * Approach: HashSet lookup
 * Complexity: O(m+n) time, O(m) space
 * Production Analogy: Filtering events by whitelist criteria
 */
import java.util.*;
public class Problem14_JewelsAndStones {
    public int numJewelsInStones(String jewels, String stones) {
        Set<Character> j = new HashSet<>();
        for (char c : jewels.toCharArray()) j.add(c);
        int count = 0;
        for (char c : stones.toCharArray()) if (j.contains(c)) count++;
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem14_JewelsAndStones().numJewelsInStones("aA", "aAAbbbb")); // 3
    }
}
