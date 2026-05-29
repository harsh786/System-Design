import java.util.*;

public class Problem46_FrogJump {
    private Map<String, Boolean> memo = new HashMap<>();

    public boolean canCross(int[] stones) {
        Set<Integer> stoneSet = new HashSet<>();
        for (int s : stones) stoneSet.add(s);
        return helper(stoneSet, stones[stones.length - 1], 0, 0);
    }

    private boolean helper(Set<Integer> stones, int last, int pos, int k) {
        String key = pos + "," + k;
        if (memo.containsKey(key)) return memo.get(key);
        if (pos == last) return true;
        boolean result = false;
        for (int jump = k - 1; jump <= k + 1; jump++) {
            if (jump > 0 && stones.contains(pos + jump)) {
                if (helper(stones, last, pos + jump, jump)) { result = true; break; }
            }
        }
        memo.put(key, result);
        return result;
    }

    public static void main(String[] args) {
        Problem46_FrogJump sol = new Problem46_FrogJump();
        System.out.println(sol.canCross(new int[]{0,1,3,5,6,8,12,17})); // true
    }
}
