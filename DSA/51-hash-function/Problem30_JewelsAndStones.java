import java.util.*;

public class Problem30_JewelsAndStones {
    public int numJewelsInStones(String jewels, String stones) {
        Set<Character> set = new HashSet<>();
        for (char c : jewels.toCharArray()) set.add(c);
        int count = 0;
        for (char c : stones.toCharArray()) if (set.contains(c)) count++;
        return count;
    }

    public static void main(String[] args) {
        Problem30_JewelsAndStones sol = new Problem30_JewelsAndStones();
        System.out.println(sol.numJewelsInStones("aA", "aAAbbbb")); // 3
    }
}
