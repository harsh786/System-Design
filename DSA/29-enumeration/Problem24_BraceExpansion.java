import java.util.*;

public class Problem24_BraceExpansion {
    public String[] expand(String s) {
        List<List<Character>> groups = new ArrayList<>();
        int i = 0;
        while (i < s.length()) {
            List<Character> group = new ArrayList<>();
            if (s.charAt(i) == '{') {
                i++;
                while (s.charAt(i) != '}') { if (s.charAt(i) != ',') group.add(s.charAt(i)); i++; }
                i++;
            } else { group.add(s.charAt(i)); i++; }
            Collections.sort(group);
            groups.add(group);
        }
        List<String> result = new ArrayList<>();
        dfs(groups, 0, new StringBuilder(), result);
        return result.toArray(new String[0]);
    }
    private void dfs(List<List<Character>> groups, int idx, StringBuilder sb, List<String> result) {
        if (idx == groups.size()) { result.add(sb.toString()); return; }
        for (char c : groups.get(idx)) { sb.append(c); dfs(groups,idx+1,sb,result); sb.deleteCharAt(sb.length()-1); }
    }
    public static void main(String[] args) { System.out.println(Arrays.toString(new Problem24_BraceExpansion().expand("{a,b}c{d,e}f"))); }
}
