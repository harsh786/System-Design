import java.util.*;

public class Problem19_MaximumLengthOfConcatenatedString {
    public int maxLength(List<String> arr) {
        return dfs(arr, 0, 0);
    }

    private int dfs(List<String> arr, int idx, int mask) {
        if (idx == arr.size()) return Integer.bitCount(mask);
        int res = dfs(arr, idx+1, mask);
        int m = 0; boolean valid = true;
        for (char c : arr.get(idx).toCharArray()) { int bit = 1<<(c-'a'); if ((m&bit)!=0) { valid=false; break; } m|=bit; }
        if (valid && (mask & m) == 0) res = Math.max(res, dfs(arr, idx+1, mask|m));
        return res;
    }

    public static void main(String[] args) { System.out.println(new Problem19_MaximumLengthOfConcatenatedString().maxLength(Arrays.asList("un","iq","ue"))); }
}
