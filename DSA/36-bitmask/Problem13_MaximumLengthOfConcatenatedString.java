import java.util.*;

public class Problem13_MaximumLengthOfConcatenatedString {
    public int maxLength(List<String> arr) {
        List<Integer> masks = new ArrayList<>();
        for (String s : arr) {
            int mask = 0; boolean dup = false;
            for (char c : s.toCharArray()) { int bit = 1 << (c - 'a'); if ((mask & bit) != 0) { dup = true; break; } mask |= bit; }
            if (!dup) masks.add(mask);
        }
        return dfs(masks, 0, 0);
    }

    private int dfs(List<Integer> masks, int idx, int cur) {
        if (idx == masks.size()) return Integer.bitCount(cur);
        int res = dfs(masks, idx + 1, cur);
        if ((cur & masks.get(idx)) == 0) res = Math.max(res, dfs(masks, idx + 1, cur | masks.get(idx)));
        return res;
    }

    public static void main(String[] args) {
        System.out.println(new Problem13_MaximumLengthOfConcatenatedString().maxLength(Arrays.asList("un","iq","ue")));
    }
}
