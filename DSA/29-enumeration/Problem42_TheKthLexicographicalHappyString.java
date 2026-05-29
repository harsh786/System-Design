public class Problem42_TheKthLexicographicalHappyString {
    int count = 0; String result = "";
    public String getHappyString(int n, int k) {
        backtrack(n, k, new StringBuilder()); return result;
    }
    private void backtrack(int n, int k, StringBuilder sb) {
        if (sb.length() == n) { count++; if (count == k) result = sb.toString(); return; }
        for (char c = 'a'; c <= 'c'; c++) {
            if (sb.length() > 0 && sb.charAt(sb.length()-1) == c) continue;
            sb.append(c); backtrack(n,k,sb); sb.deleteCharAt(sb.length()-1);
            if (!result.isEmpty()) return;
        }
    }
    public static void main(String[] args) { System.out.println(new Problem42_TheKthLexicographicalHappyString().getHappyString(3,9)); }
}
