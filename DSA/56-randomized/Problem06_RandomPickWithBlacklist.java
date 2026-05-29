import java.util.*;

public class Problem06_RandomPickWithBlacklist {
    // Map blacklisted numbers to whitelist tail
    Map<Integer, Integer> map;
    int whiteLen;
    Random rand;

    public Problem06_RandomPickWithBlacklist(int n, int[] blacklist) {
        map = new HashMap<>();
        whiteLen = n - blacklist.length;
        Set<Integer> blackSet = new HashSet<>();
        for (int b : blacklist) blackSet.add(b);
        int last = n - 1;
        for (int b : blacklist) {
            if (b < whiteLen) {
                while (blackSet.contains(last)) last--;
                map.put(b, last--);
            }
        }
        rand = new Random();
    }

    public int pick() {
        int r = rand.nextInt(whiteLen);
        return map.getOrDefault(r, r);
    }

    public static void main(String[] args) {
        Problem06_RandomPickWithBlacklist sol = new Problem06_RandomPickWithBlacklist(7, new int[]{2, 3, 5});
        for (int i = 0; i < 10; i++) System.out.print(sol.pick() + " ");
        System.out.println();
    }
}
