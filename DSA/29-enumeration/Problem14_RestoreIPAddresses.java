import java.util.*;

public class Problem14_RestoreIPAddresses {
    public List<String> restoreIpAddresses(String s) {
        List<String> result = new ArrayList<>();
        backtrack(result, new ArrayList<>(), s, 0);
        return result;
    }

    private void backtrack(List<String> result, List<String> parts, String s, int start) {
        if (parts.size() == 4) { if (start == s.length()) result.add(String.join(".", parts)); return; }
        for (int len = 1; len <= 3 && start+len <= s.length(); len++) {
            String part = s.substring(start, start+len);
            if ((part.length() > 1 && part.startsWith("0")) || Integer.parseInt(part) > 255) continue;
            parts.add(part); backtrack(result,parts,s,start+len); parts.remove(parts.size()-1);
        }
    }

    public static void main(String[] args) { System.out.println(new Problem14_RestoreIPAddresses().restoreIpAddresses("25525511135")); }
}
