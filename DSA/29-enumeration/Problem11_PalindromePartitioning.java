import java.util.*;

public class Problem11_PalindromePartitioning {
    public List<List<String>> partition(String s) {
        List<List<String>> result = new ArrayList<>();
        backtrack(result, new ArrayList<>(), s, 0);
        return result;
    }

    private void backtrack(List<List<String>> result, List<String> temp, String s, int start) {
        if (start == s.length()) { result.add(new ArrayList<>(temp)); return; }
        for (int end = start; end < s.length(); end++) {
            if (isPalin(s, start, end)) { temp.add(s.substring(start, end+1)); backtrack(result,temp,s,end+1); temp.remove(temp.size()-1); }
        }
    }

    private boolean isPalin(String s, int l, int r) { while (l<r) { if (s.charAt(l++)!=s.charAt(r--)) return false; } return true; }

    public static void main(String[] args) { System.out.println(new Problem11_PalindromePartitioning().partition("aab")); }
}
