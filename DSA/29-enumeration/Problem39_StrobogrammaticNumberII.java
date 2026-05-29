import java.util.*;

public class Problem39_StrobogrammaticNumberII {
    public List<String> findStrobogrammatic(int n) { return helper(n, n); }
    private List<String> helper(int n, int total) {
        if (n == 0) return new ArrayList<>(Arrays.asList(""));
        if (n == 1) return new ArrayList<>(Arrays.asList("0","1","8"));
        List<String> inner = helper(n-2, total);
        List<String> result = new ArrayList<>();
        for (String s : inner) {
            if (n != total) result.add("0"+s+"0");
            result.add("1"+s+"1"); result.add("6"+s+"9"); result.add("8"+s+"8"); result.add("9"+s+"6");
        }
        return result;
    }
    public static void main(String[] args) { System.out.println(new Problem39_StrobogrammaticNumberII().findStrobogrammatic(3)); }
}
