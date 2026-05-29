import java.util.*;

public class Problem47_WordBreakII {
    private Map<Integer, List<String>> memo = new HashMap<>();

    public List<String> wordBreak(String s, List<String> wordDict) {
        Set<String> dict = new HashSet<>(wordDict);
        return helper(s, dict, 0);
    }

    private List<String> helper(String s, Set<String> dict, int start) {
        if (memo.containsKey(start)) return memo.get(start);
        List<String> result = new ArrayList<>();
        if (start == s.length()) { result.add(""); return result; }
        for (int end = start + 1; end <= s.length(); end++) {
            String word = s.substring(start, end);
            if (dict.contains(word)) {
                for (String rest : helper(s, dict, end)) {
                    result.add(word + (rest.isEmpty() ? "" : " " + rest));
                }
            }
        }
        memo.put(start, result);
        return result;
    }

    public static void main(String[] args) {
        Problem47_WordBreakII sol = new Problem47_WordBreakII();
        System.out.println(sol.wordBreak("catsanddog", Arrays.asList("cat","cats","and","sand","dog")));
    }
}
