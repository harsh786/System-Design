import java.util.*;

public class Problem23_IteratorForCombination {
    private List<String> combos = new ArrayList<>();
    private int idx = 0;

    public Problem23_IteratorForCombination(String characters, int combinationLength) {
        generate(characters, combinationLength, 0, new StringBuilder());
    }
    private void generate(String s, int len, int start, StringBuilder sb) {
        if (sb.length()==len) { combos.add(sb.toString()); return; }
        for (int i = start; i < s.length(); i++) { sb.append(s.charAt(i)); generate(s,len,i+1,sb); sb.deleteCharAt(sb.length()-1); }
    }
    public String next() { return combos.get(idx++); }
    public boolean hasNext() { return idx < combos.size(); }

    public static void main(String[] args) {
        Problem23_IteratorForCombination it = new Problem23_IteratorForCombination("abc",2);
        while (it.hasNext()) System.out.println(it.next());
    }
}
