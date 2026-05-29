import java.util.*;

public class Problem41_CombinationIterator {
    private List<String> combinations = new ArrayList<>();
    private int index = 0;

    public Problem41_CombinationIterator(String characters, int combinationLength) {
        generate(characters, combinationLength, 0, new StringBuilder());
    }

    private void generate(String chars, int len, int start, StringBuilder sb) {
        if (sb.length() == len) { combinations.add(sb.toString()); return; }
        for (int i = start; i <= chars.length() - (len - sb.length()); i++) {
            sb.append(chars.charAt(i)); generate(chars, len, i + 1, sb); sb.deleteCharAt(sb.length() - 1);
        }
    }

    public String next() { return combinations.get(index++); }
    public boolean hasNext() { return index < combinations.size(); }

    public static void main(String[] args) {
        Problem41_CombinationIterator it = new Problem41_CombinationIterator("abc", 2);
        while (it.hasNext()) System.out.println(it.next());
    }
}
