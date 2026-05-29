import java.util.*;

public class Problem07_CombinationIterator {
    List<String> combinations = new ArrayList<>();
    int idx = 0;

    public Problem07_CombinationIterator(String characters, int combinationLength) {
        generate(characters, 0, new StringBuilder(), combinationLength);
    }

    void generate(String s, int start, StringBuilder sb, int len) {
        if (sb.length() == len) { combinations.add(sb.toString()); return; }
        for (int i = start; i < s.length(); i++) {
            sb.append(s.charAt(i));
            generate(s, i + 1, sb, len);
            sb.deleteCharAt(sb.length() - 1);
        }
    }

    public String next() { return combinations.get(idx++); }
    public boolean hasNext() { return idx < combinations.size(); }

    public static void main(String[] args) {
        Problem07_CombinationIterator it = new Problem07_CombinationIterator("abc", 2);
        while (it.hasNext()) System.out.println(it.next());
    }
}
