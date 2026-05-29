import java.util.*;

public class Problem21_MinimumWindowSubstringHash {
    public String minWindow(String s, String t) {
        Map<Character, Integer> need = new HashMap<>(), have = new HashMap<>();
        for (char c : t.toCharArray()) need.merge(c, 1, Integer::sum);
        int required = need.size(), formed = 0, left = 0;
        int[] ans = {-1, 0, 0};
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            have.merge(c, 1, Integer::sum);
            if (need.containsKey(c) && have.get(c).intValue() == need.get(c).intValue()) formed++;
            while (formed == required) {
                if (ans[0] == -1 || right - left + 1 < ans[0]) { ans[0] = right-left+1; ans[1] = left; ans[2] = right; }
                char lc = s.charAt(left);
                have.merge(lc, -1, Integer::sum);
                if (need.containsKey(lc) && have.get(lc) < need.get(lc)) formed--;
                left++;
            }
        }
        return ans[0] == -1 ? "" : s.substring(ans[1], ans[2] + 1);
    }

    public static void main(String[] args) {
        Problem21_MinimumWindowSubstringHash sol = new Problem21_MinimumWindowSubstringHash();
        System.out.println(sol.minWindow("ADOBECODEBANC", "ABC")); // "BANC"
    }
}
