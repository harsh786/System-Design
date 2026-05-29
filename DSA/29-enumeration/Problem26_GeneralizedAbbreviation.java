import java.util.*;

public class Problem26_GeneralizedAbbreviation {
    public List<String> generateAbbreviations(String word) {
        List<String> result = new ArrayList<>();
        backtrack(result, word, new StringBuilder(), 0, 0);
        return result;
    }
    private void backtrack(List<String> result, String word, StringBuilder sb, int idx, int count) {
        int len = sb.length();
        if (idx == word.length()) { if (count > 0) sb.append(count); result.add(sb.toString()); sb.setLength(len); return; }
        // abbreviate
        backtrack(result, word, sb, idx+1, count+1);
        // keep
        if (count > 0) sb.append(count);
        sb.append(word.charAt(idx));
        backtrack(result, word, sb, idx+1, 0);
        sb.setLength(len);
    }
    public static void main(String[] args) { System.out.println(new Problem26_GeneralizedAbbreviation().generateAbbreviations("word")); }
}
