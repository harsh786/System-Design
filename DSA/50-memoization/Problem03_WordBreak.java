import java.util.*;

public class Problem03_WordBreak {
    private Map<String, Boolean> memo = new HashMap<>();

    public boolean wordBreak(String s, List<String> wordDict) {
        if (s.isEmpty()) return true;
        if (memo.containsKey(s)) return memo.get(s);
        for (String word : wordDict) {
            if (s.startsWith(word) && wordBreak(s.substring(word.length()), wordDict)) {
                memo.put(s, true);
                return true;
            }
        }
        memo.put(s, false);
        return false;
    }

    public static void main(String[] args) {
        Problem03_WordBreak sol = new Problem03_WordBreak();
        System.out.println(sol.wordBreak("leetcode", Arrays.asList("leet","code"))); // true
    }
}
