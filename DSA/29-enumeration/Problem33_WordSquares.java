import java.util.*;

public class Problem33_WordSquares {
    public List<List<String>> wordSquares(String[] words) {
        int len = words[0].length();
        Map<String, List<String>> prefixMap = new HashMap<>();
        for (String w : words) for (int i = 0; i <= len; i++) prefixMap.computeIfAbsent(w.substring(0,i), k->new ArrayList<>()).add(w);
        List<List<String>> result = new ArrayList<>();
        for (String w : words) { List<String> square = new ArrayList<>(); square.add(w); backtrack(result,square,len,prefixMap); }
        return result;
    }
    private void backtrack(List<List<String>> result, List<String> square, int len, Map<String,List<String>> map) {
        if (square.size()==len) { result.add(new ArrayList<>(square)); return; }
        int idx = square.size();
        StringBuilder prefix = new StringBuilder();
        for (int i = 0; i < idx; i++) prefix.append(square.get(i).charAt(idx));
        List<String> candidates = map.getOrDefault(prefix.toString(), Collections.emptyList());
        for (String c : candidates) { square.add(c); backtrack(result,square,len,map); square.remove(square.size()-1); }
    }
    public static void main(String[] args) { System.out.println(new Problem33_WordSquares().wordSquares(new String[]{"area","lead","wall","lady","ball"})); }
}
